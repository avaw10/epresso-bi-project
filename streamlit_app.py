"""Main app. Checkpoint 0: loads a file and shows a profile.
Keep calculations in analytics.py and the assistant in agent.py."""
from pathlib import Path
import streamlit as st
import pandas as pd
import agent
import importlib
importlib.reload(agent)
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

st.markdown("""
<div style="
    background-color: #F8F5F0;
    padding: 28px 32px;
    border-radius: 16px;
    border-left: 6px solid #A47754;
    margin-bottom: 24px;
">
    <h1 style="
        color: #543A2A;
        margin: 0;
        font-size: 38px;
        font-weight: 750;
    ">
        ☕ E-Presso
    </h1>
    <p style="
        color: #A47754;
        font-size: 13px;
        letter-spacing: 3px;
        font-weight: 700;
        margin: 8px 0;
    ">
        BUSINESS INTELLIGENCE
    </p>
    <p style="
        color: #6F594B;
        font-size: 16px;
        margin: 0;
    ">
        Your business performance, brewed into insights.
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* KPI metric cards */
div[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E8D8C4;
    border-radius: 16px;
    padding: 14px 16px;
    box-shadow: 0 4px 14px rgba(84, 58, 42, 0.06);
}

/* KPI labels */
div[data-testid="stMetricLabel"] {
    color: #8C6A52;
    font-weight: 600;
}

/* KPI numbers */
div[data-testid="stMetricValue"] {
    color: #543A2A;
    font-weight: 700;
}

/* Subtle hover effect */
div[data-testid="stMetric"]:hover {
    border-color: #A47754;
    box-shadow: 0 6px 18px rgba(84, 58, 42, 0.12);
    transition: all 0.2s ease;
}

/* Warm latte sidebar */
section[data-testid="stSidebar"] {
    background-color: #E8D8C4;
}

/* Sidebar text */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] label {
    color: #543A2A;
}

/* Multiselect dropdowns */
div[data-baseweb="select"] > div {
    background-color: #FFFFFF;
    border: 1px solid #D8C5B2;
    border-radius: 10px;
}

/* Dropdown focus */
div[data-baseweb="select"] > div:focus-within {
    border-color: #A47754;
}

/* Selected filter tags */
span[data-baseweb="tag"] {
    background-color: #E8D8C4;
    border-radius: 6px;
}

/* File uploader */
section[data-testid="stFileUploaderDropzone"] {
    background-color: #F8F5F0;
    border: 1px dashed #A47754;
    border-radius: 12px;
}


/* AI Assistant welcome section */
.assistant-welcome {
    background: #FFFFFF;
    border: 1px solid #E8D8C4;
    border-left: 5px solid #A47754;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
}

.assistant-eyebrow {
    color: #A47754;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 2px;
}

.assistant-welcome h2 {
    color: #543A2A;
    margin: 8px 0;
}

.assistant-welcome p {
    color: #6F594B;
    margin-bottom: 0;
}

/* Chat message cards */
div[data-testid="stChatMessage"] {
    background-color: #FFFFFF;
    border: 1px solid #E8D8C4;
    border-radius: 14px;
    padding: 12px;
}

/* Chat input */
div[data-testid="stChatInput"] {
    border-radius: 14px;
}

/* Calculation details */
div[data-testid="stExpander"] {
    border: 1px solid #E8D8C4;
    border-radius: 12px;
    background-color: #FFFFFF;
}


/* Assistant response styling */
div[data-testid="stChatMessage"] {
    background: #FFFFFF;
    border: 1px solid #E8D8C4;
    border-radius: 16px;
    padding: 20px 24px;
    box-shadow: 0 3px 12px rgba(84, 58, 42, 0.04);
}

/* Headings within assistant responses */
div[data-testid="stChatMessage"] h4 {
    color: #543A2A;
    font-weight: 700;
    margin-bottom: 12px;
}

/* Subtle section dividers */
div[data-testid="stChatMessage"] hr {
    border-color: #E8D8C4;
    margin: 16px 0;
}

/* Scope caption */
div[data-testid="stChatMessage"] [data-testid="stCaptionContainer"] {
    color: #A47754;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}

/* Calculation details */
div[data-testid="stChatMessage"] [data-testid="stExpander"] {
    background: #F8F5F0;
    border: 1px solid #E8D8C4;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


def style_coffee_chart(fig, color="#A47754"):
    """Apply the E-Presso coffeehouse theme to a Plotly chart."""
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#543A2A", family="Arial"),
        title_font=dict(size=18, color="#543A2A"),
        margin=dict(l=35, r=35, t=65, b=45),
        colorway=["#A47754", "#543A2A", "#C9A88B"],
        xaxis=dict(
            showgrid=True,
            gridcolor="#F0E7DD",
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F0E7DD",
            zeroline=False,
        ),
    )
    fig.update_traces(
        marker_color=color,
        selector=dict(type="bar"),
    )
    fig.update_traces(
        line=dict(color=color, width=3),
        marker=dict(color=color, size=9),
        selector=dict(type="scatter"),
    )
    return fig


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

    quality_col1, quality_col2, quality_col3, quality_col4 = st.columns(4)

    if selected_table == "Sales":
        quality_col1.metric(
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

        quality_col2.metric(
            "Sales with Invalid Product IDs",
            int((~df["Product ID"].isin(products_df["Product ID"])).sum())
        )
        quality_col3.metric(
            "Sales with Invalid Category IDs",
            int((~df["Category ID"].isin(categories_df["Category ID"])).sum())
        )
        quality_col4.metric(
            "Sales with Invalid Store IDs",
            int((~df["Store ID"].isin(stores_df["ID"])).sum())
        )

    elif selected_table == "Products":
        quality_col1.metric(
            "Duplicate Product IDs",
            int(df["Product ID"].duplicated().sum())
        )

    elif selected_table == "Categories":
        quality_col1.metric(
            "Duplicate Category IDs",
            int(df["Category ID"].duplicated().sum())
        )

    elif selected_table == "Stores":
        quality_col1.metric(
            "Duplicate Store IDs",
            int(df["ID"].duplicated().sum())
        )

    elif selected_table == "Survey Results":
        quality_col1.metric(
            "Duplicate Survey IDs",
            int(df["Survey ID"].duplicated().sum())
        )
        stores_df = cached_load(
            DEFAULT_FILES["Stores"].read_bytes(),
            DEFAULT_FILES["Stores"].name,
            0
        )

        quality_col2.metric(
            "Survey Records with Invalid Store IDs",
            int((~df["Store ID"].isin(stores_df["ID"])).sum())
        )

        quality_col3.metric(
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

    
    with st.expander("View Dataset Relationships"):
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
        - Uses distinct store-year combinations to avoid duplicating survey responses.
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
    # Preserve the full survey dataset for the AI assistant
    assistant_survey_df = survey_df.copy()

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
        # Preserve all sales records for the AI assistant
    assistant_sales_df = merged_df.copy()

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

    
    # Dashboard filter section
    st.markdown("### ☕ Dashboard Filters")
    st.caption("Select one or more filters to explore your business performance.")

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

    if merged_df.empty:
        st.info(
            "No sales data matches the selected filters. "
            "Try changing or clearing one or more filters."
        )

    # Calculate revenue AFTER applying filters
    total_revenue = analytics.calculate_total_revenue(merged_df)

    revenue_col, satisfaction_col, growth_col = st.columns(3)
    growth_percentage = analytics.calculate_year_over_year_growth(merged_df)

    with growth_col:
        st.metric(
            label="Year-over-Year Revenue Growth",
            value=f"{growth_percentage:+.2f}%"
            if growth_percentage is not None
            else "N/A"
        )

    with revenue_col:
        st.metric(
            label="Total Revenue",
            value=f"${total_revenue:,.2f}"
        )
         # -----------------------------------
    # CUSTOMER SATISFACTION
    # -----------------------------------

    # Find the stores and years included in the filtered sales data
    filtered_survey = analytics.filter_survey_by_sales(
        survey_df, merged_df
    )

    # Calculate average customer satisfaction
    average_satisfaction = analytics.calculate_average_satisfaction(filtered_survey)


    # Display the metric
    with satisfaction_col:
        st.metric(
            label="Average Store Customer Satisfaction",
            value=f"{average_satisfaction:.2f} / 5"
            if pd.notna(average_satisfaction)
            else "No survey data"
        )
        st.caption(
            "Customer satisfaction is based on store-level survey responses, not individual product categories."
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
    satisfaction_by_market = analytics.calculate_satisfaction_by_market(survey_with_stores)


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
        st.plotly_chart(style_coffee_chart(fig_satisfaction), width="stretch")


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
        tickvals=revenue_by_year["Year"].tolist(),
        tickangle=0,
        title="Year"
    )

    fig.update_yaxes(title="Total Revenue")

    # Display chart in left column
    with chart_col1:
        st.plotly_chart(style_coffee_chart(fig, "#543A2A"), width="stretch")

     # -----------------------------------
    # TOTAL REVENUE BY MARKET
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
        st.plotly_chart(
            style_coffee_chart(fig_store),
            width="stretch"
    )

    # -----------------------------------
    # PERCENTAGE OF REVENUE PER MONTH
    # -----------------------------------

    # Extract the month from the Date column
    merged_df["Month"] = merged_df["Date"].dt.month

    # Calculate monthly revenue percentages in analytics.py
    revenue_by_month = analytics.calculate_monthly_revenue_percentage(merged_df)

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
        st.plotly_chart(style_coffee_chart(fig_month, "#C9A88B"), width="stretch")

with tab_assistant:

    
    st.markdown("""
    <div class="assistant-welcome">
        <div class="assistant-eyebrow">E-PRESSO INTELLIGENCE</div>
        <h2>☕ Ask E-Presso AI</h2>
        <p>
            Explore your business data, compare performance,
            and uncover insights through conversation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "The AI Assistant uses all E-Presso data, regardless of your "
        "Dashboard filters. To see specific results, include a year "
        "or market in your question."
    )
    st.session_state.setdefault("n_questions", 0)
    st.session_state.setdefault("history", [])
   
    st.markdown("### Conversation")

    # Display previous questions and answers
    for item in st.session_state["history"]:
        with st.chat_message("user", avatar=":material/person:"):
            st.write(item["question"])

        
        with st.chat_message(
            "assistant",
            avatar=":material/analytics:"
        ):
            answer = item["answer"]

            # Show the scope in a subtle caption
            st.caption(f"SCOPE · {answer['scope']}")

            # Main findings
            st.markdown("#### Findings")
            st.markdown(answer["findings"])

            st.divider()

            # Interpretation
            st.markdown("**Interpretation**")
            st.write(
                answer["interpretation"]
                or "No additional interpretation is supported."
            )

            # Next steps
            st.markdown("**Suggested Next Steps**")
            st.write(
                answer["next_steps"]
                or "No recommendation is supported by this data."
            )

            # Keep technical evidence available
            with st.expander("View calculation details"):
                st.json(answer["tool_log"])


    # Accept a new question
    question = st.chat_input("Ask a question about the loaded data")

    if question:
        if st.session_state["n_questions"] >= MAX_QUESTIONS:
            st.warning(
                "Question limit reached for this session."
            )
        else:
            st.session_state["n_questions"] += 1

            assistant_df = assistant_sales_df.copy()

            # Add Year for revenue questions
            if selected_table == "Sales":
                assistant_df["Year"] = pd.to_datetime(
                    assistant_df["Date"]
                ).dt.year

            # Ask the rules-based assistant
            answer = agent.answer_question(
                question,
                assistant_df,
                mode="llm",
                survey_df=assistant_survey_df
            )


            # Save the answer to chat history
            st.session_state["history"].append({
                "question": question,
                "answer": answer
            })

            st.rerun()
