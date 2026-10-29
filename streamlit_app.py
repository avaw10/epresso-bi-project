"""E-Presso source loading and profiling checkpoint."""
from zipfile import BadZipFile

import pandas as pd
import streamlit as st

import analytics

st.set_page_config(page_title='BI Analyst for E-Presso', layout='wide')
st.title('BI Analyst for E-Presso')
st.caption('Stage 3: validate the raw Sales revenue total before adding joins, filters, or charts.')


@st.cache_data(show_spinner=False)
def cached_load_epresso_sources(sales_bytes: bytes, stores_bytes: bytes, survey_bytes: bytes):
    return analytics.load_epresso_sources(sales_bytes, stores_bytes, survey_bytes)


with st.sidebar:
    st.header('E-Presso source files')
    sales_file = st.file_uploader(
        'Sales workbook (Sales, Products, and Categories sheets)',
        type=['xlsx', 'xlsm', 'xls'],
        key='sales_workbook',
    )
    stores_file = st.file_uploader(
        'Stores file (tab-delimited CSV)',
        type=['csv', 'tsv', 'txt'],
        key='stores_file',
    )
    survey_file = st.file_uploader(
        'Survey workbook',
        type=['xlsx', 'xlsm', 'xls'],
        key='survey_workbook',
    )

if not all((sales_file, stores_file, survey_file)):
    st.info('Upload all three source files in the sidebar to view their independent profiles.')
    st.stop()

try:
    tables = cached_load_epresso_sources(
        sales_file.getvalue(),
        stores_file.getvalue(),
        survey_file.getvalue(),
    )
except (ValueError, OSError, KeyError, UnicodeError, BadZipFile, pd.errors.ParserError) as exc:
    st.error(f'Could not load the E-Presso source files: {exc}')
    st.stop()

tab_profiles, tab_dashboard, tab_assistant = st.tabs(
    ['Data and profile', 'Dashboard', 'Assistant'],
)

with tab_profiles:
    st.subheader('Source profiles')
    st.caption('Tables are shown separately. No joins or revenue calculations have been performed.')

    for table_name, df in tables.items():
        spec = analytics.SOURCE_TABLES[table_name]
        with st.expander(table_name, expanded=table_name == 'Sales'):
            st.markdown(f"**Grain:** {spec['grain']}")
            profile = analytics.profile_table(df)
            key_profile = analytics.profile_key(df, spec['key_columns'])
            c1, c2, c3 = st.columns(3)
            c1.metric('Rows', f"{profile['rows']:,}")
            c2.metric('Columns', profile['columns'])
            c3.metric('Exact duplicate rows', profile['duplicate_rows'])
            st.markdown(
                f"**Candidate grain key:** {', '.join(key_profile['columns'])}  \n"
                f"Unique combinations: {key_profile['unique_values']:,} / {len(df):,}; "
                f"missing-key rows: {key_profile['missing_rows']:,}; "
                f"duplicate-key rows: {key_profile['duplicate_rows']:,}"
            )
            st.dataframe(df.head(50), use_container_width=True)
            left, right = st.columns(2)
            left.markdown('**Missing values**')
            left.dataframe(profile['missing'], use_container_width=True)
            right.markdown('**Data types**')
            right.dataframe(profile['dtypes'], use_container_width=True)

    st.info('Compare the single revenue result with Power BI before adding dashboard features.')

with tab_dashboard:
    revenue = analytics.get_total(tables['Sales'], 'Revenue')
    if revenue.error:
        st.error(f'Could not calculate total revenue: {revenue.error}')
    else:
        st.metric('Total Revenue (source currency)', f'{revenue.value:,.2f}')
        st.caption(
            f"Sum of the Sales table's Revenue column across all {revenue.rows_used:,} "
            'usable rows. No joins or filters are applied. Revenue is not profit.'
        )
        st.warning('Reconcile this figure with Power BI before adding filters or charts.')

with tab_assistant:
    st.info('The assistant comes after the $1,000 test, as required by the project instructions.')
