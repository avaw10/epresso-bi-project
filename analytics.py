"""Business logic. Keep Streamlit code OUT of this file so every function can be
tested on its own and reused by the assistant."""
from __future__ import annotations

import io
from dataclasses import asdict, dataclass, field
from unicodedata import name

import pandas as pd

EXCEL_EXT = ('.xlsx', '.xlsm', '.xls')
TEXT_EXT = ('.csv', '.txt', '.tsv')


# ---------------------------------------------------------------- loading
def excel_sheet_names(file_bytes: bytes) -> list[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


def load_table(file_bytes: bytes, filename: str, sheet_name=0) -> pd.DataFrame:
    """Read an uploaded CSV / TXT / TSV / Excel file into a DataFrame."""
    name = filename.lower()
    buffer = io.BytesIO(file_bytes)
    if name.endswith(EXCEL_EXT):
        if "survey" in filename.casefold() or "survey" in str(sheet_name).casefold():
            return pd.read_excel(buffer, sheet_name=sheet_name, header=2)

        return pd.read_excel(buffer, sheet_name=sheet_name)
    if name.endswith(TEXT_EXT):
        first_line = file_bytes.decode("utf-8-sig").splitlines()[0]
        separator = "\t" if first_line.count("\t") > first_line.count(",") else ","
        return pd.read_csv(buffer, sep=separator)

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
def _require_columns(df: pd.DataFrame, columns, table_name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        names = ', '.join(repr(column) for column in missing)
        raise ValueError(f'{table_name} is missing required column(s): {names}.')


def count_missing_or_non_numeric(df: pd.DataFrame, column: str) -> int:
    """Count blank or non-numeric values in a column intended to be numeric."""
    _require_columns(df, [column], 'Data')
    return int(pd.to_numeric(df[column], errors='coerce').isna().sum())


def check_merge(
    left: pd.DataFrame,
    right: pd.DataFrame,
    on=None,
    value_col: str = 'Revenue',
    how: str = 'left',
    *,
    left_on=None,
    right_on=None,
    validate: str | None = None,
):
    """Merge and report row/revenue changes. Returns (merged, report)."""
    if on is None and (left_on is None or right_on is None):
        raise ValueError('Specify either `on` or both `left_on` and `right_on`.')

    left_keys = on if on is not None else left_on
    right_keys = on if on is not None else right_on
    left_keys = [left_keys] if isinstance(left_keys, str) else list(left_keys)
    right_keys = [right_keys] if isinstance(right_keys, str) else list(right_keys)
    if len(left_keys) != len(right_keys):
        raise ValueError('The left and right merge keys must have the same number of columns.')

    _require_columns(left, [*left_keys, value_col], 'Left table')
    _require_columns(right, right_keys, 'Right table')

    before_rows = len(left)
    before_sum = float(pd.to_numeric(left[value_col], errors='coerce').sum())
    # pandas matches null keys to other null keys. Excluding them prevents blank
    # dimension keys from creating accidental matches or multiplying sales.
    right_with_keys = right.dropna(subset=right_keys)
    merge_keys = {'on': on} if on is not None else {
        'left_on': left_on, 'right_on': right_on,
    }
    try:
        merged = left.merge(
            right_with_keys, how=how, validate=validate, **merge_keys,
        )
    except pd.errors.MergeError as exc:
        raise ValueError(
            'The right table has duplicate merge-key values; resolve them before merging.'
        ) from exc
    after_rows = len(merged)
    after_sum = float(pd.to_numeric(merged[value_col], errors='coerce').sum())
    changed = after_rows != before_rows or abs(after_sum - before_sum) > 1e-9
    report = {
        'rows_before': before_rows, 'rows_after': after_rows,
        'sum_before': before_sum, 'sum_after': after_sum,
        'changed': changed,
        'warning': ('The join changed the row count or the total. Check the grain and keys '
                    'of both tables before using this result.') if changed else '',
    }
    return merged, report


def calculate_total_revenue(sales_df):
    """Sum valid revenue values; blanks are reported separately as data quality."""
    _require_columns(sales_df, ['Revenue'], 'Sales dataset')
    return float(pd.to_numeric(sales_df['Revenue'], errors='coerce').sum())


def merge_sales_products(sales_df, products_df):
    """Merge sales with product names using Product ID."""
    return check_merge(
        sales_df, products_df, on='Product ID', value_col='Revenue',
        how='left', validate='many_to_one',
    )


def merge_sales_categories(sales_df, categories_df):
    """Add category information to sales records."""
    return check_merge(
        sales_df, categories_df, on='Category ID', value_col='Revenue',
        how='left', validate='many_to_one',
    )


def merge_sales_stores(sales_df, stores_df):
    """Merge sales with store information using Store ID."""
    return check_merge(
        sales_df, stores_df, left_on='Store ID', right_on='ID',
        value_col='Revenue', how='left', validate='many_to_one',
    )

def calculate_revenue_by_year(df):
    """Calculate total revenue for each year."""
    revenue_by_year = (
        df.groupby("Year")["Revenue"]
        .sum()
        .reset_index()
        .sort_values("Year")
    )
    return revenue_by_year

def calculate_revenue_by_market(df):
    """Calculate total revenue for each market."""
    revenue_by_market = (
        df.groupby("Market")["Revenue"]
        .sum()
        .reset_index()
        .sort_values("Revenue", ascending=True)
    )
    return revenue_by_market

def calculate_monthly_revenue_percentage(df):
    """Calculate each month's share of total filtered revenue."""
    revenue_by_month = (
        df.groupby("Month")["Revenue"]
        .sum()
        .reset_index()
        .sort_values("Month")
    )

    total_revenue = revenue_by_month["Revenue"].sum()

    revenue_by_month["Percentage"] = (
        revenue_by_month["Revenue"] / total_revenue * 100
        if total_revenue != 0
        else 0.0
    )

    return revenue_by_month

def calculate_average_satisfaction(filtered_survey):
    """Calculate average satisfaction from survey responses."""
    satisfaction = pd.to_numeric(
        filtered_survey["Satisfaction"],
        errors="coerce"
    )
    return satisfaction.mean()

def calculate_satisfaction_by_market(survey_with_stores):
    """Calculate average customer satisfaction for each market."""
    satisfaction_by_market = (
        survey_with_stores.groupby("Market")["Satisfaction"]
        .mean()
        .reset_index()
        .dropna(subset=["Satisfaction"])
        .sort_values("Satisfaction", ascending=True)
    )
    return satisfaction_by_market


def filter_survey_by_sales(survey_df, filtered_sales_df):
    """Match survey responses to stores and years in filtered sales."""

    # Find unique store-year combinations in filtered sales
    active_store_years = filtered_sales_df[
        ["Store ID", "Year"]
    ].drop_duplicates().copy()

    # Make a copy so we don't modify the original survey
    survey = survey_df.copy()

    # Convert survey years (e.g., Y2025) to numbers
    survey["Year"] = pd.to_numeric(
        survey["Year"].astype(str).str.replace("Y", "", regex=False),
        errors="coerce"
    )

    active_store_years["Year"] = pd.to_numeric(
        active_store_years["Year"],
        errors="coerce"
    )

    # Match survey responses to the selected stores and years
    filtered_survey = survey.merge(
        active_store_years,
        on=["Store ID", "Year"],
        how="inner"
    )

    return filtered_survey


def get_average_satisfaction(df) -> ToolResult:
    """Calculate average customer satisfaction from survey responses."""

    if "Satisfaction" not in df.columns:
        return _error(
            "get_average_satisfaction",
            "Survey data does not contain a Satisfaction column."
        )

    scores = pd.to_numeric(df["Satisfaction"], errors="coerce")
    valid_scores = scores.dropna()

    if valid_scores.empty:
        return _error(
            "get_average_satisfaction",
            "No valid satisfaction scores were found."
        )

    return ToolResult(
        tool="get_average_satisfaction",
        value=float(valid_scores.mean()),
        definition="Average customer satisfaction across valid survey responses.",
        scope={"dataset": "Survey Results", "filters": {}},
        rows_used=len(valid_scores),
        caveats=[
            "This is an average of survey responses, not all customers.",
            "The result does not establish why customers are satisfied or dissatisfied."
        ]
    )

def greatest_store_revenue_decline(df: pd.DataFrame) -> ToolResult:
    """Find the largest store revenue decline between consecutive years."""

    name = "greatest_store_revenue_decline"
    required = ["Store ID", "Year", "Revenue"]

    for col in required:
        if col not in df.columns:
            return _error(name, f"Missing required column: {col}")

    work = df[required].copy()
    work["Revenue"] = pd.to_numeric(work["Revenue"], errors="coerce")
    work = work.dropna(subset=required)

    yearly = (
        work.groupby(["Store ID", "Year"])["Revenue"]
        .sum()
        .reset_index()
        .sort_values(["Store ID", "Year"])
    )

    yearly["Previous Year"] = yearly.groupby("Store ID")["Year"].shift(1)
    yearly["Previous Revenue"] = yearly.groupby("Store ID")["Revenue"].shift(1)

    # Compare only consecutive years with positive prior revenue.
    comparisons = yearly[
        (yearly["Year"] - yearly["Previous Year"] == 1)
        & (yearly["Previous Revenue"] > 0)
    ].copy()

    comparisons["Percentage Change"] = (
        (comparisons["Revenue"] - comparisons["Previous Revenue"])
        / comparisons["Previous Revenue"]
        * 100
    )

    declines = comparisons[comparisons["Percentage Change"] < 0]

    if declines.empty:
        return _error(name, "No year-over-year store revenue declines found.")

    worst = declines.loc[declines["Percentage Change"].idxmin()]

    return ToolResult(
        tool=name,
        value={
            "store_id": str(worst["Store ID"]),
            "previous_year": int(worst["Previous Year"]),
            "year": int(worst["Year"]),
            "previous_revenue": float(worst["Previous Revenue"]),
            "current_revenue": float(worst["Revenue"]),
            "percentage_change": float(worst["Percentage Change"])
        },
        definition="Largest year-over-year percentage revenue decline by store.",
        scope={"dataset": "Sales", "filters": "All stores and years"},
        rows_used=len(work),
        caveats=[
            "Compares consecutive years only.",
            "Excludes comparisons with zero or negative prior-year revenue.",
            "A percentage decline does not establish the cause."
        ]
    )

def greatest_store_revenue_increase(df: pd.DataFrame) -> ToolResult:
    """Find the largest store revenue increase between consecutive years."""

    name = "greatest_store_revenue_increase"
    required = ["Store ID", "Year", "Revenue"]

    for col in required:
        if col not in df.columns:
            return _error(name, f"Missing required column: {col}")

    work = df[required].copy()
    work["Revenue"] = pd.to_numeric(work["Revenue"], errors="coerce")
    work["Year"] = pd.to_numeric(work["Year"], errors="coerce")
    work = work.dropna(subset=required)

    yearly = (
        work.groupby(["Store ID", "Year"])["Revenue"]
        .sum()
        .reset_index()
        .sort_values(["Store ID", "Year"])
    )

    yearly["Previous Year"] = yearly.groupby("Store ID")["Year"].shift(1)
    yearly["Previous Revenue"] = yearly.groupby("Store ID")["Revenue"].shift(1)

    # Compare consecutive years with positive prior revenue.
    comparisons = yearly[
        (yearly["Year"] - yearly["Previous Year"] == 1)
        & (yearly["Previous Revenue"] > 0)
    ].copy()

    comparisons["Percentage Change"] = (
        (comparisons["Revenue"] - comparisons["Previous Revenue"])
        / comparisons["Previous Revenue"]
        * 100
    )

    increases = comparisons[comparisons["Percentage Change"] > 0]

    if increases.empty:
        return _error(name, "No year-over-year store revenue increases found.")

    best = increases.loc[increases["Percentage Change"].idxmax()]

    return ToolResult(
        tool=name,
        value={
            "store_id": str(best["Store ID"]),
            "previous_year": int(best["Previous Year"]),
            "year": int(best["Year"]),
            "previous_revenue": float(best["Previous Revenue"]),
            "current_revenue": float(best["Revenue"]),
            "percentage_change": float(best["Percentage Change"])
        },
        definition="Largest year-over-year percentage revenue increase by store.",
        scope={"dataset": "Sales", "filters": "All stores and years"},
        rows_used=len(work),
        caveats=[
            "Compares consecutive years only.",
            "Excludes comparisons with zero or negative prior-year revenue.",
            "A percentage increase does not establish the cause."
        ]
    )

def compare_store_revenue_growth(
    df: pd.DataFrame,
    start_year: int,
    end_year: int,
    metric: str
) -> ToolResult:
    """Find the store with the greatest revenue growth between two years."""

    name = "compare_store_revenue_growth"
    required = ["Store ID", "Year", "Revenue"]

    for col in required:
        if col not in df.columns:
            return _error(name, f"Missing required column: {col}")

    if metric not in {"percentage", "dollars"}:
        return _error(name, "Metric must be 'percentage' or 'dollars'.")

    if end_year <= start_year:
        return _error(name, "End year must be after start year.")

    work = df[required].copy()
    work["Year"] = pd.to_numeric(work["Year"], errors="coerce")
    work["Revenue"] = pd.to_numeric(work["Revenue"], errors="coerce")
    work = work.dropna(subset=required)

    work = work[work["Year"].isin([start_year, end_year])]

    yearly = (
        work.groupby(["Store ID", "Year"])["Revenue"]
        .sum()
        .unstack()
    )

    if start_year not in yearly.columns or end_year not in yearly.columns:
        return _error(name, "One or both years have no revenue data.")

    # Only compare stores with records in both years.
    yearly = yearly.dropna(subset=[start_year, end_year]).copy()

    # Percentage growth requires a positive starting revenue.
    if metric == "percentage":
        yearly = yearly[yearly[start_year] > 0]

    if yearly.empty:
        return _error(name, "No stores have comparable revenue data.")

    yearly["Dollar Change"] = yearly[end_year] - yearly[start_year]

    if metric == "percentage":
        yearly["Percentage Change"] = (
            yearly["Dollar Change"] / yearly[start_year] * 100
        )
        winner_id = yearly["Percentage Change"].idxmax()
    else:
        winner_id = yearly["Dollar Change"].idxmax()

    winner = yearly.loc[winner_id]

    if winner["Dollar Change"] <= 0:
        return _error(name, "No store experienced revenue growth.")

    percentage_change = (
        winner["Dollar Change"] / winner[start_year] * 100
        if winner[start_year] > 0
        else None
    )

    return ToolResult(
        tool=name,
        value={
            "store_id": str(winner_id),
            "start_year": int(start_year),
            "end_year": int(end_year),
            "start_revenue": float(winner[start_year]),
            "end_revenue": float(winner[end_year]),
            "dollar_change": float(winner["Dollar Change"]),
            "percentage_change": (
                float(percentage_change)
                if percentage_change is not None
                else None
            ),
            "metric": metric
        },
        definition=f"Greatest store revenue growth measured in {metric}.",
        scope={
            "dataset": "Sales",
            "filters": f"{start_year} to {end_year}"
        },
        rows_used=len(work),
        caveats=[
            "Only includes stores with revenue records in both years.",
            *(
                ["Percentage growth requires positive starting revenue."]
                if metric == "percentage"
                else []
            ),
            "Revenue growth does not establish the cause."
        ]
    )
def get_store_revenue_declines(
    df: pd.DataFrame,
    start_year: int,
    end_year: int
) -> ToolResult:
    """Find all stores with declining revenue between two years."""

    name = "get_store_revenue_declines"
    required = ["Store ID", "Year", "Revenue"]

    for col in required:
        if col not in df.columns:
            return _error(name, f"Missing required column: {col}")

    if end_year <= start_year:
        return _error(name, "End year must be after start year.")

    work = df[required].copy()
    work["Year"] = pd.to_numeric(work["Year"], errors="coerce")
    work["Revenue"] = pd.to_numeric(work["Revenue"], errors="coerce")
    work = work.dropna(subset=required)
    work = work[work["Year"].isin([start_year, end_year])]

    yearly = (
        work.groupby(["Store ID", "Year"])["Revenue"]
        .sum()
        .unstack()
    )

    if start_year not in yearly.columns or end_year not in yearly.columns:
        return _error(name, "One or both years have no revenue data.")

    yearly = yearly.dropna(subset=[start_year, end_year]).copy()
    yearly = yearly[yearly[start_year] > 0].copy()

    if yearly.empty:
        return _error(name, "No stores have comparable revenue data.")

    yearly["Dollar Change"] = yearly[end_year] - yearly[start_year]
    yearly["Percentage Change"] = (
        yearly["Dollar Change"] / yearly[start_year] * 100
    )

    declines = yearly[yearly["Dollar Change"] < 0].copy()
    declines = declines.sort_values("Percentage Change")

    stores = []
    for store_id, row in declines.iterrows():
        stores.append({
            "store_id": str(store_id),
            "start_revenue": float(row[start_year]),
            "end_revenue": float(row[end_year]),
            "dollar_change": float(row["Dollar Change"]),
            "percentage_change": float(row["Percentage Change"])
        })

    return ToolResult(
        tool=name,
        value={
            "start_year": int(start_year),
            "end_year": int(end_year),
            "declining_store_count": len(stores),
            "compared_store_count": len(yearly),
            "stores": stores
        },
        definition=(
            "Dollar change = end-year revenue - start-year revenue. "
            "Percentage change = dollar change / start-year revenue * 100."
        ),
        scope={
            "dataset": "Sales",
            "filters": f"{start_year} to {end_year}"
        },
        rows_used=len(work),
        caveats=[
            "Only compares stores with records in both years.",
            "Excludes stores with zero or negative starting revenue.",
            "Revenue decline does not establish the cause."
        ]
    )
