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
st.caption('Upload a file or use the already uploaded files to explore the data and ask questions.')


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
    st.subheader("Dataset Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", f"{profile['rows']:,}")
    c2.metric("Columns", profile["columns"])
    c3.metric("Duplicate Rows", profile["duplicate_rows"])

    st.subheader("Data Quality Checks")

    if selected_table == "Sales":
        st.metric(
            "Duplicate Sales IDs",
            int(df["Sales ID"].duplicated().sum())
        )

        products_df = cached_load(
            DEFAULT_FILES["Products"].read_bytes(),
            DEFAULT_FILES["Products"].name,
            "Products"
        )
        categories_df = cached_load(
            DEFAULT_FILES["Categories"].read_bytes(),
            DEFAULT_FILES["Categories"].name,
            "Categories"
        )
        stores_df = cached_load(
            DEFAULT_FILES["Stores"].read_bytes(),
            DEFAULT_FILES["Stores"].name,
            0
        )

        st.metric(
            "Sales with Invalid Product IDs",
            int((~df["Product ID"].isin(products_df["Product ID"])).sum())
        )
        st.metric(
            "Sales with Invalid Category IDs",
            int((~df["Category ID"].isin(categories_df["Category ID"])).sum())
        )
        st.metric(
            "Sales with Invalid Store IDs",
            int((~df["Store ID"].isin(stores_df["ID"])).sum())
        )

    elif selected_table == "Products":
        st.metric(
            "Duplicate Product IDs",
            int(df["Product ID"].duplicated().sum())
        )

    elif selected_table == "Categories":
        st.metric(
            "Duplicate Category IDs",
            int(df["Category ID"].duplicated().sum())
        )

    elif selected_table == "Stores":
        st.metric(
            "Duplicate Store IDs",
            int(df["ID"].duplicated().sum())
        )

    elif selected_table == "Survey Results":
        st.metric(
            "Duplicate Survey IDs",
            int(df["Survey ID"].duplicated().sum())
        )
        stores_df = cached_load(
            DEFAULT_FILES["Stores"].read_bytes(),
            DEFAULT_FILES["Stores"].name,
            0
        )

        st.metric(
            "Survey Records with Invalid Store IDs",
            int((~df["Store ID"].isin(stores_df["ID"])).sum())
        )

        st.metric(
            "Duplicate Survey Records",
            int(df.duplicated().sum())
        )

    st.subheader("Preview")
    st.dataframe(df.head(50))

    left, right = st.columns(2)
    left.subheader("Missing Values")
    left.dataframe(profile["missing"])
    right.subheader("Data Types")
    right.dataframe(profile["dtypes"])

    st.subheader("Dataset Relationships")
    st.markdown("""
    **Sales → Products**
    - Joined using Product ID.
    - Identifies which products were sold.

    **Sales → Categories**
    - Joined using Category ID.
    - Identifies product categories.

    **Sales → Stores**
    - Sales Store ID matches Stores ID.
    - Adds store location, market, and store type.

    **Survey Results → Stores**
    - Connected using Store ID.
    - Associates satisfaction responses with stores.

    **Survey Results → Sales**
    - Matched using Store ID and Year.
    - Uses distinct store-year combinations to avoid
      duplicating survey responses.
    """)

with tab_dash:
    st.header("E-Presso Business Performance")

    sales_file = DEFAULT_FILES["Sales"]
    products_file = DEFAULT_FILES["Products"]
    categories_file = DEFAULT_FILES["Categories"]
    stores_file = DEFAULT_FILES["Stores"]

    def dashboard_table(table_name, fallback_path, fallback_sheet):
     # Use the uploaded file only for the selected dataset
        if uploaded is not None and selected_table == table_name:
            return df

        # Otherwise, use the original dataset
        return cached_load(
            fallback_path.read_bytes(),
            fallback_path.name,
            fallback_sheet
        )

    sales_df = dashboard_table("Sales", sales_file, "Sales")
    products_df = dashboard_table("Products", products_file, "Products")
    categories_df = dashboard_table("Categories", categories_file, "Categories")
    stores_df = dashboard_table("Stores", stores_file, "Stores")

    survey_file = DEFAULT_FILES["Survey Results"]

    survey_df = dashboard_table(
        "Survey Results",
        survey_file,
        "Survey Results"
    )

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

    try:
        merged_df, categories_report = analytics.merge_sales_categories(
            merged_df, categories_df
        )
    except ValueError as exc:
        st.error(f"Sales + Categories merge failed: {exc}")
        st.stop()

    try:
        merged_df, stores_report = analytics.merge_sales_stores(
            merged_df, stores_df
        )
    except ValueError as exc:
        st.error(f"Sales + Stores merge failed: {exc}")
        st.stop()

    merged_df["Year"] = pd.to_datetime(merged_df["Date"]).dt.year

    # -----------------------------------
    # DASHBOARD FILTERS
    # -----------------------------------

    # Create Year and Month columns
    merged_df["Year"] = pd.to_datetime(merged_df["Date"]).dt.year
    merged_df["Month"] = pd.to_datetime(merged_df["Date"]).dt.month

    # Month names
    month_names = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
    ]

    # Arrange filters in three columns
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_years = st.multiselect(
            "Year",
            options=sorted(merged_df["Year"].dropna().unique()),
            default=[],
            placeholder="All Years"
        )

        selected_store_types = st.multiselect(
            "Store Type",
            options=sorted(merged_df["StoreType"].dropna().unique()),
            default=[],
            placeholder="All Store Types"
        )

    with col2:
        selected_months = st.multiselect(
            "Month",
            options=month_names,
            default=[],
            placeholder="All Months"
        )

        selected_markets = st.multiselect(
            "Market",
            options=sorted(merged_df["Market"].dropna().unique()),
            default=[],
            placeholder="All Markets"
        )

    with col3:
        selected_categories = st.multiselect(
            "Category",
            options=sorted(merged_df["Category"].dropna().unique()),
            default=[],
            placeholder="All Categories"
        )

        selected_states = st.multiselect(
            "State",
            options=sorted(merged_df["State"].dropna().unique()),
            default=[],
            placeholder="All States"
        )

    # -----------------------------------
    # APPLY FILTERS
    # -----------------------------------

    # Year
    if selected_years:
        merged_df = merged_df[
            merged_df["Year"].isin(selected_years)
        ]

    # Month
    if selected_months:
        selected_month_numbers = [
            month_names.index(month) + 1
            for month in selected_months
        ]

        merged_df = merged_df[
            merged_df["Month"].isin(selected_month_numbers)
        ]

    # Category
    if selected_categories:
        merged_df = merged_df[
            merged_df["Category"].isin(selected_categories)
        ]

    # Store Type
    if selected_store_types:
        merged_df = merged_df[
            merged_df["StoreType"].isin(selected_store_types)
        ]

    # Market
    if selected_markets:
        merged_df = merged_df[
            merged_df["Market"].isin(selected_markets)
        ]

    # State
    if selected_states:
        merged_df = merged_df[
            merged_df["State"].isin(selected_states)
        ]

    # Calculate revenue AFTER applying filters
    total_revenue = analytics.calculate_total_revenue(merged_df)

    revenue_col, satisfaction_col = st.columns(2)

    with revenue_col:
        st.metric(
            label="Total Revenue",
            value=f"${total_revenue:,.2f}"
        )
         # -----------------------------------
    # CUSTOMER SATISFACTION
    # -----------------------------------

    # Find the stores and years included in the filtered sales data
    active_store_years = merged_df[
        ["Store ID", "Year"]
    ].drop_duplicates()

       # Remove the "Y" from survey years (Y2025 becomes 2025)
    survey_df["Year"] = pd.to_numeric(
        survey_df["Year"].astype(str).str.replace("Y", "", regex=False),
        errors="coerce"
    )

    active_store_years["Year"] = pd.to_numeric(
        active_store_years["Year"], errors="coerce"
    )

    # Match survey results to those stores and years
    filtered_survey = survey_df.merge(
        active_store_years,
        on=["Store ID", "Year"],
        how="inner"
    )

    # Calculate average customer satisfaction
    average_satisfaction = pd.to_numeric(
        filtered_survey["Satisfaction"],
        errors="coerce"
    ).mean()

    # Display the metric
    with satisfaction_col:
        st.metric(
            label="Average Customer Satisfaction",
            value=f"{average_satisfaction:.2f} / 5"
            if pd.notna(average_satisfaction)
            else "No survey data"
        )

        # -----------------------------------
    # CUSTOMER SATISFACTION BY MARKET
    # -----------------------------------

    # Connect survey responses to store information
    survey_with_stores = filtered_survey.merge(
        stores_df[["ID", "Market"]],
        left_on="Store ID",
        right_on="ID",
        how="left"
    )

        # Calculate average satisfaction by market
    satisfaction_by_market = (
        survey_with_stores.groupby("Market")["Satisfaction"]
        .mean()
        .reset_index()
        .dropna(subset=["Satisfaction"])
        .sort_values("Satisfaction", ascending=True)
    )

    # Create horizontal bar chart
    chart_col1, chart_col2 = st.columns(2)

    fig_satisfaction = px.bar(
        satisfaction_by_market,
        x="Satisfaction",
        y="Market",
        orientation="h",
        title="Average Customer Satisfaction by Market",
        labels={
            "Satisfaction": "Average Satisfaction (1–5)",
            "Market": "Market"
        }
    )

    # Show satisfaction scores at the end of each bar
    fig_satisfaction.update_traces(
        texttemplate="%{x:.2f}",
        textposition="outside",
        cliponaxis=False
    )

    fig_satisfaction.update_layout(
        margin=dict(l=100, r=65, t=60, b=40)
    )

    # Show both axes when data is available
    fig_satisfaction.update_xaxes(
        title_text="Average Satisfaction (1–5)",
        range=[0, 5],
        visible=True
    )

    fig_satisfaction.update_yaxes(
        title_text="Market",
        visible=True,
        automargin=True
    )

    # Display a message when no survey data is available
    if satisfaction_by_market.empty:
        fig_satisfaction.add_annotation(
            text="No customer satisfaction data available for the selected filters",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=16, color="gray")
        )

        fig_satisfaction.update_xaxes(visible=False)
        fig_satisfaction.update_yaxes(visible=False)

    with chart_col2:
        st.plotly_chart(fig_satisfaction, width="stretch")


   # TOTAL REVENUE BY YEAR
    # -----------------------------------

    # Convert dates and extract the year
    merged_df["Date"] = pd.to_datetime(merged_df["Date"])
    merged_df["Year"] = merged_df["Date"].dt.year

    # Calculate revenue by year
    revenue_by_year = analytics.calculate_revenue_by_year(merged_df)

    # Create line chart
    fig = px.line(
        revenue_by_year,
        x="Year",
        y="Revenue",
        title="Total Revenue by Year",
        markers=True
    )

    fig.update_yaxes(
        tickformat="$,.0f",
        range=[0, revenue_by_year["Revenue"].max() * 1.2]
    )

    # Format years without commas
    fig.update_xaxes(
        tickmode="array",
        tickvals=[2025, 2026, 2027, 2028, 2029],
        ticktext=["2025", "2026", "2027", "2028", "2029"],
        tickangle=0,
        title="Year"
    )

    fig.update_yaxes(title="Total Revenue")

    # Display chart in left column
    with chart_col1:
        st.plotly_chart(fig, width="stretch")

     # -----------------------------------
    # TOTAL REVENUE BY STORE TYPE
    # -----------------------------------

    revenue_by_store_type = analytics.calculate_revenue_by_market(merged_df)

    fig_store = px.bar(
        revenue_by_store_type,
        x="Revenue",
        y="Market",
        orientation="h",
        title="Total Revenue by Market",
        labels={
            "Revenue": "Total Revenue",
            "Market": "Market"
        }
    )
    # Display chart in right column
    with chart_col2:
        st.plotly_chart(fig_store, width="stretch")

    # -----------------------------------
    # PERCENTAGE OF REVENUE PER MONTH
    # -----------------------------------

    # Extract the month from the Date column
    merged_df["Month"] = merged_df["Date"].dt.month

    # Calculate revenue by month
    revenue_by_month = (
        merged_df.groupby("Month")["Revenue"]
        .sum()
        .reset_index()
        .sort_values("Month")
    )

    # Calculate each month's percentage of total revenue
    revenue_by_month["Percentage"] = (
        revenue_by_month["Revenue"]
        / revenue_by_month["Revenue"].sum() * 100
    )

    # Create the chart
    fig_month = px.bar(
        revenue_by_month,
        x="Month",
        y="Percentage",
        title="Percentage of Revenue per Month",
        labels={
            "Month": "Month",
            "Percentage": "Percentage of Total Revenue (%)"
        }
    )

    # Display month names horizontally
    fig_month.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=[
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ],
        tickangle=0
    )

    # Display chart in left column
    with chart_col1:
        st.plotly_chart(fig_month, width="stretch")

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
