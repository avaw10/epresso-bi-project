"""Business logic. Keep Streamlit code OUT of this file so every function can be
tested on its own and reused by the assistant."""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field

import pandas as pd

EXCEL_EXT = ('.xlsx', '.xlsm', '.xls')
TEXT_EXT = ('.csv', '.txt', '.tsv')

SOURCE_TABLES = {
    'Sales': {
        'grain': 'One row per store, date, and product combination.',
        'key_columns': ['Date', 'Store ID', 'Product ID'],
    },
    'Products': {
        'grain': 'One row per product.',
        'key_columns': ['Product ID'],
    },
    'Categories': {
        'grain': 'One row per product category.',
        'key_columns': ['Category ID'],
    },
    'Stores': {
        'grain': 'One row per store or sales channel.',
        'key_columns': ['ID'],
    },
    'Survey Results': {
        'grain': 'One row per store and survey year.',
        'key_columns': ['Store ID', 'Year'],
    },
}


# ---------------------------------------------------------------- loading
def excel_sheet_names(file_bytes: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


def _read_required_sheet(file_bytes: bytes, sheet_name: str,
                         required_columns: set[str], header=0) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=header)
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f'Sheet {sheet_name!r} is missing required columns: {sorted(missing)}')
    return df


def load_epresso_sources(sales_bytes: bytes, stores_bytes: bytes,
                         survey_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Load each E-Presso source table independently; do not join tables here."""
    sales_sheets = set(excel_sheet_names(sales_bytes))
    required_sales_sheets = {'Sales', 'Products', 'Categories'}
    missing_sheets = required_sales_sheets - sales_sheets
    if missing_sheets:
        raise ValueError(f'Sales workbook is missing sheets: {sorted(missing_sheets)}')

    tables = {
        'Sales': _read_required_sheet(
            sales_bytes, 'Sales',
            {'Sales ID', 'Date', 'Store ID', 'StoreYear', 'Category ID', 'Product ID', 'Revenue'},
        ),
        'Products': _read_required_sheet(
            sales_bytes, 'Products', {'Product ID', 'Product'},
        ),
        'Categories': _read_required_sheet(
            sales_bytes, 'Categories', {'Category ID', 'Category'},
        ),
    }

    stores = pd.read_csv(
        io.BytesIO(stores_bytes), sep='\t',
        dtype={'ID': 'string', 'PostalCode': 'string'},
    )
    required_store_columns = {
        'ID', 'City', 'State', 'PostalCode', 'Phone', 'StoreType',
        'Market', 'Location', 'Manager',
    }
    missing_store_columns = required_store_columns - set(stores.columns)
    if missing_store_columns:
        raise ValueError(f'Stores file is missing required columns: {sorted(missing_store_columns)}')
    tables['Stores'] = stores

    tables['Survey Results'] = _read_required_sheet(
        survey_bytes, 'Survey Results',
        {'Survey ID', 'Store ID', 'Year', 'Satisfaction', 'Interest'},
        header=2,
    )
    return tables


def load_table(file_bytes: bytes, filename: str, sheet_name=0) -> pd.DataFrame:
    """Read an uploaded CSV / TXT / TSV / Excel file into a DataFrame."""
    name = filename.lower()
    buffer = io.BytesIO(file_bytes)
    if name.endswith(EXCEL_EXT):
        return pd.read_excel(buffer, sheet_name=sheet_name)
    if name.endswith(TEXT_EXT):
        return pd.read_csv(buffer, sep=None, engine='python')  # sniffs the delimiter
    raise ValueError(f'Unsupported file type: {filename}')


def profile_table(df: pd.DataFrame) -> dict:
    """Basic profile: size, duplicates, missing values, data types."""
    missing = df.isna().sum()
    return {
        'rows': len(df),
        'columns': df.shape[1],
        'duplicate_rows': int(df.duplicated().sum()),
        'missing': pd.DataFrame({
            'column': missing.index,
            'missing': missing.values,
            'pct_missing': (missing.values / max(len(df), 1) * 100).round(2),
        }),
        'dtypes': pd.DataFrame({'column': df.columns, 'dtype': df.dtypes.astype(str).values}),
    }


def profile_key(df: pd.DataFrame, key_columns: list[str]) -> dict:
    """Check completeness and uniqueness of a proposed table key."""
    missing_columns = set(key_columns) - set(df.columns)
    if missing_columns:
        raise ValueError(f'Unknown key column(s): {sorted(missing_columns)}')
    missing_key = df[key_columns].isna().any(axis=1)
    complete_keys = df.loc[~missing_key, key_columns]
    return {
        'columns': key_columns,
        'missing_rows': int(missing_key.sum()),
        'duplicate_rows': int(complete_keys.duplicated().sum()),
        'unique_values': int(len(complete_keys.drop_duplicates())),
    }


# ---------------------------------------------------------- tool contract
@dataclass
class ToolResult:
    """Every analytical function returns this. The assistant may only narrate it.
    Keep `value` to plain Python types (numbers, strings, dicts, lists)."""
    tool: str
    value: object
    definition: str
    scope: dict
    rows_used: int
    caveats: list = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _error(tool: str, message: str, scope: dict | None = None) -> ToolResult:
    return ToolResult(tool=tool, value=None, definition='', scope=scope or {},
                      rows_used=0, caveats=[], error=message)


def _apply_filters(df: pd.DataFrame, filters: dict | None):
    """Validate filters against the LOADED data, then apply them."""
    for col, wanted in (filters or {}).items():
        if col not in df.columns:
            return df, f'Unknown column: {col}'
        wanted_list = list(wanted) if isinstance(wanted, (list, tuple, set)) else [wanted]
        valid = set(df[col].dropna().unique())
        bad = [w for w in wanted_list if w not in valid]
        if bad:
            examples = sorted(map(str, valid))[:20]
            return df, f'{bad} not found in column {col}. Valid values include: {examples}'
        df = df[df[col].isin(wanted_list)]
    return df, None


# ------------------------------------------------------ analytical tools
def get_total(df: pd.DataFrame, value_col: str, filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column, optionally filtered. EXAMPLE tool: replace the
    generic column names with your own definition of revenue."""
    name = 'get_total'
    if value_col not in df.columns:
        return _error(name, f'Unknown column: {value_col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    values = pd.to_numeric(subset[value_col], errors='coerce')
    n_bad = int(values.isna().sum())
    caveats = ['This is a sum of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) had a missing or non-numeric {value_col} and were excluded.')
    return ToolResult(tool=name, value=float(values.sum()), definition=f'Sum of {value_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(values.notna().sum()), caveats=caveats)


def group_total(df: pd.DataFrame, value_col: str, group_col: str,
                filters: dict | None = None) -> ToolResult:
    """Sum of one numeric column by group (store, channel, year, ...)."""
    name = 'group_total'
    for col in (value_col, group_col):
        if col not in df.columns:
            return _error(name, f'Unknown column: {col}')
    subset, err = _apply_filters(df, filters)
    if err:
        return _error(name, err, {'filters': filters})
    work = subset.assign(**{value_col: pd.to_numeric(subset[value_col], errors='coerce')})
    n_bad = int(work[value_col].isna().sum())
    n_nogroup = int(work[group_col].isna().sum())
    grouped = work.dropna(subset=[value_col, group_col]).groupby(group_col)[value_col].sum()
    caveats = ['Sums of the chosen column. Revenue is not profit.']
    if n_bad:
        caveats.append(f'{n_bad} row(s) with missing or non-numeric {value_col} were excluded.')
    if n_nogroup:
        caveats.append(f'{n_nogroup} row(s) with a missing {group_col} were excluded.')
    return ToolResult(tool=name, value={str(k): float(v) for k, v in grouped.items()},
                      definition=f'Sum of {value_col} by {group_col}',
                      scope={'filters': filters or 'none (all rows)'},
                      rows_used=int(len(work) - n_bad - n_nogroup), caveats=caveats)


def data_quality_report(df: pd.DataFrame) -> ToolResult:
    """Row count, duplicate rows, and missing values per column."""
    missing = {c: int(n) for c, n in df.isna().sum().items() if n > 0}
    caveats = []
    if missing:
        caveats.append('Missing values may limit conclusions drawn from those columns.')
    return ToolResult(tool='data_quality_report',
                      value={'rows': len(df), 'duplicate_rows': int(df.duplicated().sum()),
                             'columns_with_missing': missing},
                      definition='Counts of duplicate rows and missing values in the loaded table',
                      scope={'filters': 'none (full table)'}, rows_used=len(df), caveats=caveats)


# ------------------------------------------------------------ merge check
def check_merge(left: pd.DataFrame, right: pd.DataFrame, on, value_col: str, how: str = 'left'):
    """Merge, and report whether the join changed the row count or the revenue sum.
    `value_col` must be a numeric column in `left`. Returns (merged, report)."""
    before_rows = len(left)
    before_sum = float(pd.to_numeric(left[value_col], errors='coerce').sum())
    merged = left.merge(right, on=on, how=how)
    after_rows = len(merged)
    after_sum = float(pd.to_numeric(merged[value_col], errors='coerce').sum())
    fan_out = after_rows > before_rows or abs(after_sum - before_sum) > 1e-9
    report = {
        'rows_before': before_rows, 'rows_after': after_rows,
        'sum_before': before_sum, 'sum_after': after_sum,
        'changed': fan_out,
        'warning': ('The join changed the row count or the total. Check the grain and keys '
                    'of both tables before using this result.') if fan_out else '',
    }
    return merged, report
