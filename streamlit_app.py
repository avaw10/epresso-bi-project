"""Main app. Checkpoint 0: loads a file and shows a profile.
Keep calculations in analytics.py and the assistant in agent.py."""
from pathlib import Path
import streamlit as st
import pandas as pd
import agent
import analytics
import plotly.express as px

MAX_QUESTIONS = 15  # per-session limit for the assistant

DATA_FOLDER = Path(__file__).resolve().parent / "data"

DEFAULT_FILES = {
    "Sales": DATA_FOLDER / "Support Sales.xlsx",
    "Products": DATA_FOLDER / "Support Sales.xlsx",
    "Categories": DATA_FOLDER / "Support Sales.xlsx",
    "Stores": DATA_FOLDER / "Support_EX_B_Stores (3).csv",
    "Survey Results": DATA_FOLDER / "Support_EX_B_Survey (1).xlsx",
}
st.set_page_config(page_title='E-Presso Dashboard Analyst', layout='wide')
st.title('E-Presso Dashboard Analyst')
st.caption('Upload a file to explore the data and ask questions.')


@st.cache_data(show_spinner=False)
def cached_load(file_bytes: bytes, filename: str, sheet_name):
    # The cache is keyed on the file CONTENTS, so a modified file is never
    # confused with the original one.
    return analytics.load_table(file_bytes, filename, sheet_name)


def display_merge_report(title: str, report: dict) -> None:
    st.subheader(title)
    st.write("Rows before:", report["rows_before"])
    st.write("Rows after:", report["rows_after"])
    st.write("Revenue before:", f"${report['sum_before']:,.2f}")
    st.write("Revenue after:", f"${report['sum_after']:,.2f}")
    if report["changed"]:
        st.error(report["warning"])
        st.stop()
    st.success("Merge passed: row count and revenue are unchanged.")


with st.sidebar:
    st.header("Data")

    selected_table = st.selectbox(
        "Select a dataset",
        list(DEFAULT_FILES.keys())
    )

    uploaded = st.file_uploader(
        "Upload a replacement CSV or Excel file (optional)",
        type=["csv", "txt", "tsv", "xlsx", "xls"],
        key=f"upload_{selected_table}"
    )

try:
    replacement_sheets = []
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        filename = uploaded.name

        if filename.lower().endswith(analytics.EXCEL_EXT):
            sheets = analytics.excel_sheet_names(file_bytes)
            replacement_sheets = sheets
            sheet = st.sidebar.selectbox(
                "Replacement file sheet",
                sheets,
                index=sheets.index(selected_table)
                if selected_table in sheets else 0
            )
        else:
            sheet = 0

    else:
        file_path = DEFAULT_FILES[selected_table]
        file_bytes = file_path.read_bytes()
        filename = file_path.name

        if selected_table in ["Sales", "Products", "Categories"]:
            sheet = selected_table
        elif selected_table == "Survey Results":
            sheet = "Survey Results"
        else:
            sheet = 0

    df = cached_load(file_bytes, filename, sheet)

except Exception as exc:
    st.error(f"Could not load {selected_table}: {exc}")
    st.stop()

tab_data, tab_dash, tab_assistant = st.tabs(['Data and profile', 'Dashboard', 'Assistant'])

with tab_data:
    profile = analytics.profile_table(df)
    c1, c2, c3 = st.columns(3)
    c1.metric('Rows', f"{profile['rows']:,}")
    c2.metric('Columns', profile['columns'])
    c3.metric('Duplicate rows', profile['duplicate_rows'])
    st.subheader('Preview')
    st.dataframe(df.head(50))
    left, right = st.columns(2)
    left.subheader('Missing values')
    left.dataframe(profile['missing'])
    right.subheader('Data types')
    right.dataframe(profile['dtypes'])

with tab_dash:
    st.header("E-Presso Business Dashboard")

    sales_file = DEFAULT_FILES["Sales"]
    products_file = DEFAULT_FILES["Products"]
    categories_file = DEFAULT_FILES["Categories"]
    stores_file = DEFAULT_FILES["Stores"]

    def dashboard_table(table_name, fallback_path, fallback_sheet):
        if uploaded is not None and table_name in replacement_sheets:
            return cached_load(file_bytes, filename, table_name)
        if selected_table == table_name:
            return df
        return cached_load(
            fallback_path.read_bytes(), fallback_path.name, fallback_sheet
        )

    sales_df = dashboard_table("Sales", sales_file, "Sales")
    products_df = dashboard_table("Products", products_file, "Products")
    categories_df = dashboard_table("Categories", categories_file, "Categories")
    stores_df = dashboard_table("Stores", stores_file, "Stores")

    for source_df, column, table_name in (
        (products_df, "Product", "Products table"),
        (categories_df, "Category", "Categories table"),
    ):
        if column not in source_df.columns:
            st.error(f"{table_name} is missing required column: {column}")
            st.stop()

    if "ID" not in stores_df.columns:
        st.error("Stores table is missing required column: ID")
        st.stop()

    try:
        merged_df, products_report = analytics.merge_sales_products(
            sales_df, products_df
        )
    except ValueError as exc:
        st.error(f"Sales + Products merge failed: {exc}")
        st.stop()
    display_merge_report("Merge Validation: Sales + Products", products_report)

    try:
        merged_df, categories_report = analytics.merge_sales_categories(
            merged_df, categories_df
        )
    except ValueError as exc:
        st.error(f"Sales + Categories merge failed: {exc}")
        st.stop()
    display_merge_report("Merge Validation: Sales + Categories", categories_report)

    try:
        merged_df, stores_report = analytics.merge_sales_stores(
            merged_df, stores_df
        )
    except ValueError as exc:
        st.error(f"Sales + Stores merge failed: {exc}")
        st.stop()
    display_merge_report("Merge Validation: Sales + Stores", stores_report)

    st.subheader("Merge Quality Checks")

    st.write(
        "Missing or non-numeric Revenue values:",
        analytics.count_missing_or_non_numeric(sales_df, "Revenue"),
    )
    st.write("Blank Product ID keys in Products:", products_df["Product ID"].isna().sum())
    st.write("Blank Category ID keys in Categories:", categories_df["Category ID"].isna().sum())
    st.write("Blank ID keys in Stores:", stores_df["ID"].isna().sum())
    st.write("Missing product names:", merged_df["Product"].isna().sum())
    st.write("Missing category names:", merged_df["Category"].isna().sum())
    st.write("Missing store matches:", merged_df["ID"].isna().sum())

    st.subheader("Merged Data: Sales + Products + Categories + Stores")

    st.dataframe(merged_df.head(20))

    total_revenue = analytics.calculate_total_revenue(merged_df)

    st.subheader("Total Revenue by Year")

    # Convert dates and extract the year
    merged_df["Date"] = pd.to_datetime(merged_df["Date"])
    merged_df["Year"] = merged_df["Date"].dt.year

    # Calculate revenue by year
    revenue_by_year = (
        merged_df.groupby("Year")["Revenue"]
        .sum()
        .reset_index()
        .sort_values("Year")
    )
    revenue_by_year["Year"] = revenue_by_year["Year"].astype(str)

    # Create ONE line chart
    fig = px.line(
        revenue_by_year,
        x="Year",
        y="Revenue",
        title="Total Revenue by Year",
        markers=True
    )

    fig.update_xaxes(
        tickmode="array",
        tickvals=[2025, 2026, 2027, 2028, 2029],
        ticktext=["2025", "2026", "2027", "2028", "2029"],
        tickangle=0,
        title="Year"
    )

    fig.update_yaxes(title="Total Revenue ($)")

    st.plotly_chart(fig, use_container_width=True)

    st.metric(
        label="Total Revenue",
        value=f"${total_revenue:,.2f}"
    )

with tab_assistant:
    st.caption('Mode: rules-based starter. Describe what you actually built here.')
    st.session_state.setdefault('n_questions', 0)
    st.session_state.setdefault('history', [])
    for item in st.session_state['history']:
        with st.chat_message('user'):
            st.write(item['question'])
        with st.chat_message('assistant'):
            st.markdown(f"**Scope:** {item['answer']['scope']}")
            st.markdown(f"**Findings:** {item['answer']['findings']}")
            if item['answer']['interpretation']:
                st.markdown(f"**Interpretation:** {item['answer']['interpretation']}")
            with st.expander('Tool-call log'):
                st.json(item['answer']['tool_log'])
    question = st.chat_input('Ask a question about the loaded data')
    if question:
        if st.session_state['n_questions'] >= MAX_QUESTIONS:
            st.warning('Question limit reached for this session. Reload the page to start over.')
        else:
            st.session_state['n_questions'] += 1
            answer = agent.answer_question(question, df, mode='rules')
            st.session_state['history'].append({'question': question, 'answer': answer})
            st.rerun()
