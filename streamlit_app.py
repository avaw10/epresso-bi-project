"""Main app. Checkpoint 0: loads a file and shows a profile.
Keep calculations in analytics.py and the assistant in agent.py."""
from pathlib import Path
import streamlit as st

import agent
import analytics

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
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        filename = uploaded.name

        if filename.lower().endswith(analytics.EXCEL_EXT):
            sheets = analytics.excel_sheet_names(file_bytes)
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

    if selected_table != "Sales":
        st.info("Select the Sales dataset to view revenue.")
    else:
        total_revenue = analytics.calculate_total_revenue(df)

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
