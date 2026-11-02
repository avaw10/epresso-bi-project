"""Assistant: a dispatcher plus a router.
The router (rules now, a language model later) only CHOOSES a tool and its
arguments. Our code RUNS the tool. Nothing here executes model-written code."""
from __future__ import annotations
import streamlit as st
from openai import OpenAI
import analytics
from analytics import ToolResult

def get_openai_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# The ONLY things the assistant may do. Add your own tools here.
TOOLS = {
    'get_total': {
        'fn': analytics.get_total,
        'params': {'value_col', 'filters'},
        'description': 'Sum a numeric column, optionally filtered.',
    },
    'group_total': {
        'fn': analytics.group_total,
        'params': {'value_col', 'group_col', 'filters'},
        'description': 'Sum a numeric column by group (store, channel, year, ...).',
    },
    'data_quality_report': {
        'fn': analytics.data_quality_report,
        'params': set(),
        'description': 'Report duplicates and missing values in the loaded data.',
    },
       'get_average_satisfaction': {
        'fn': analytics.get_average_satisfaction,
        'params': set(),
        'description': 'Calculate average customer satisfaction from survey responses.',
    },
      'greatest_store_revenue_decline': {
        'fn': analytics.greatest_store_revenue_decline,
        'params': set(),
        'description': (
            'Find the store with the greatest percentage revenue '
            'decline between consecutive years.'
        ),
        },
        'greatest_store_revenue_increase': {
        'fn': analytics.greatest_store_revenue_increase,
        'params': set(),
        'description': (
            'Find the store with the greatest percentage revenue '
            'increase between consecutive years.'
        ),
        },
        'compare_store_revenue_growth': {
        'fn': analytics.compare_store_revenue_growth,
        'params': {'start_year', 'end_year', 'metric'},
        'description': (
            'Find the store with the greatest revenue increase between '
            'two specified years, measured by percentage or dollars.'
        ),
     },
        'get_store_revenue_declines': {
        'fn': analytics.get_store_revenue_declines,
        'params': {'start_year', 'end_year'},
        'description': (
            'Find all stores with declining revenue between two '
            'specified years. Return dollar changes, percentage '
            'changes, and counts for detailed tables or summaries.'
        ),
    },

}

UNSUPPORTED = ("I can't answer that question reliably with my current analytical tools. "
    "I can calculate revenue, compare revenue across years, and check "
    "for missing or duplicate data.\n\n"
    "**Suggested next step:** We may need additional analysis or data "
    "to investigate your question.")

# For when you add a language model: keep these rules in the system prompt.
SYSTEM_PROMPT = """You are an analytical assistant for E-Presso managers.
Rules:
- Only state numbers that appear in a tool result. Never estimate or recall figures.
- Always call a tool before making a numerical claim.
- State the scope (which filters/period) of every answer.
- Separate Findings (from tool results), Interpretation, and Next steps.
- Revenue is not profit. Association is not causation.
- If the data cannot support a conclusion, say so and name the missing information.
- Never ask for, run, or write code. Never modify data."""

def run_tool(name: str, args: dict, df, log: list, survey_df=None) -> ToolResult:
    """Validate, execute, and log approved analytical tools."""

    if name not in TOOLS:
        result = analytics._error(name, f"Unknown tool: {name}")

    else:
        unexpected = set(args) - TOOLS[name]["params"]

        if unexpected:
            result = analytics._error(
                name,
                f"Unexpected argument(s): {sorted(unexpected)}"
            )

        elif name == "get_average_satisfaction":
            if survey_df is None:
                result = analytics._error(
                    name,
                    "Survey data is not available."
                )
            else:
                result = TOOLS[name]["fn"](survey_df, **args)

        else:
            result = TOOLS[name]["fn"](df, **args)

    log.append({
        "tool": name,
        "arguments": args,
        "result": result.to_dict()
    })

    return result

def rules_router(question: str, df):
    """Choose an approved analytical function based on the question."""
    q = question.lower()

    # Do not treat causal questions as simple calculations
    causal_phrases = (
        "why ",
        "what caused",
        "what led to",
        "what explains",
        "reason for",
    )

    if any(phrase in q for phrase in causal_phrases):
        return None

    # Questions about missing data or duplicates
    if any(w in q for w in ('missing', 'duplicate', 'quality', 'blank')):
        return 'data_quality_report', {}

    
    # Questions about revenue
    if 'revenue' in q:
          # Questions asking for revenue across all years
        if any(phrase in q for phrase in (
            'each year',
            'every year',
            'by year',
            'yearly',
            'annual revenue'
        )):
            return 'group_total', {
                'value_col': 'Revenue',
                'group_col': 'Year',
                'filters': None
            }
            # Recognize questions comparing two years
        years_mentioned = [
            year for year in [2025, 2026, 2027, 2028, 2029]
            if str(year) in q
        ]

        if len(years_mentioned) == 2:
            return 'group_total', {
                'value_col': 'Revenue',
                'group_col': 'Year',
                'filters': {'Year': years_mentioned}
            }
        
        # Reject years that are not available in the loaded data
        import re

        requested_years = re.findall(r"\b(?:19|20)\d{2}\b", q)

        available_years = set(df["Year"].dropna().astype(int))

        for requested_year in requested_years:
            if int(requested_year) not in available_years:
                return None
        # Check whether the question mentions a year
        years = [2025, 2026, 2027, 2028, 2029]

        for year in years:
            if str(year) in q:
                return 'get_total', {
                    'value_col': 'Revenue',
                    'filters': {'Year': year}
                }

        # If no year is mentioned, calculate total revenue
        if any(w in q for w in ('total', 'overall', 'all')):
            return 'get_total', {
                'value_col': 'Revenue',
                'filters': None
            }

    return None


def llm_router(question, df):
    """Use OpenAI to select an approved analytical tool."""

    import json

    client = get_openai_client()

    # Only tools in this list can be selected by the LLM.
    tools = [
        {
            "type": "function",
            "name": "get_total",
            "description": "Calculate total revenue, optionally for a specific year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value_col": {
                        "type": "string",
                        "enum": ["Revenue"]
                    },
                    
                    "filters": {
                        "type": "object",
                        "properties": {
                            "Year": {
                                "type": ["integer", "null"]
                            }
                        },
                        "required": ["Year"],
                        "additionalProperties": False
                    }
                },
                "required": ["value_col", "filters"],
                "additionalProperties": False
            },
            "strict": True
        },
        {
            "type": "function",
            "name": "group_total",
            "description": (
                "Calculate revenue grouped by Year or Market. "
                "Use Market when asked which market has the highest or lowest "
                "revenue, or to compare revenue across markets. "
                "Use Year for revenue trends or comparisons across years."
            ),            "parameters": {
                "type": "object",
                "properties": {
                    "value_col": {
                        "type": "string",
                        "enum": ["Revenue"]
                    },
                    "group_col": {
                        "type": "string",
                        "enum": ["Year", "Market"]
                    },
                    "filters": {
                        "type": "object",
                        "properties": {
                            "Year": {
                                "type": ["array", "null"],
                                "items": {
                                    "type": "integer"
                                }
                            }
                        },
                        "required": ["Year"],
                        "additionalProperties": False
                    }
                },
                "required": ["value_col", "group_col", "filters"],
                "additionalProperties": False
            },
            "strict": True
        },
        {
            "type": "function",
            "name": "data_quality_report",
            "description": "Check for missing values and duplicate records.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        },
                {
            "type": "function",
            "name": "get_average_satisfaction",
            "description": (
                "Calculate the overall average customer satisfaction "
                "score from Survey Results. Use this when the user "
                "asks about average or overall customer satisfaction."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        },

        {
            "type": "function",
            "name": "greatest_store_revenue_decline",
            "description": (
                "Find which store experienced the greatest percentage "
                "revenue decline between any two consecutive years. "
                "Use for questions about the largest or worst "
                "year-over-year store revenue decline. "
                "Does not support comparisons restricted to specific years."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        },

        {
            "type": "function",
            "name": "greatest_store_revenue_increase",
            "description": (
                "Find which store experienced the greatest percentage "
                "revenue increase between any two consecutive years. "
                "Use for questions about the largest or best "
                "year-over-year store revenue increase. "
                "Does not support comparisons restricted to specific years."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False
            },
            "strict": True
        },

            
        {
            "type": "function",
            "name": "compare_store_revenue_growth",
            "description": (
                "Find the store with the greatest revenue increase between "
                "two specified years. Use metric='percentage' for the highest "
                "percentage growth, or metric='dollars' for the largest "
                "dollar increase. Requires a start year and end year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_year": {
                        "type": "integer",
                        "description": "The starting year, such as 2028."
                    },
                    "end_year": {
                        "type": "integer",
                        "description": "The ending year, such as 2029."
                    },
                    "metric": {
                        "type": "string",
                        "enum": ["percentage", "dollars"],
                        "description": "How to measure revenue growth."
                    }
                },
                "required": ["start_year", "end_year", "metric"],
                "additionalProperties": False
            },
            "strict": True
        },

        {
            "type": "function",
            "name": "get_store_revenue_declines",
            "description": (
                "Find all stores with declining revenue between two specified "
                "years. Return each store's revenue, dollar change, and "
                "percentage change, along with counts. Use for questions "
                "requesting either a full table or a summary of declining stores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_year": {
                        "type": "integer",
                        "description": "The starting year, such as 2028."
                    },
                    "end_year": {
                        "type": "integer",
                        "description": "The ending year, such as 2029."
                    }
                },
                "required": ["start_year", "end_year"],
                "additionalProperties": False
            },
            "strict": True
        },

    ]

    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=(
            "You are a tool-selection assistant for E-Presso. "
            "Choose only an available analytical function. "
            "Never calculate numbers yourself. "
            "If the question cannot be answered using the "
            "available functions, do not call a tool. "
            "Do not invent columns, years, or filters."
        ),
        input=(
            f"Available years: "
            f"{sorted(df['Year'].dropna().astype(int).unique().tolist())}. "
            f"Question: {question}"
        ),
        tools=tools,
        tool_choice="auto"
    )

    for item in response.output:
            if item.type == "function_call":
                args = json.loads(item.arguments)

                # Remove empty year filters before calling Python
                if "filters" in args:
                    filters = args["filters"]

                    if filters is None:
                        args["filters"] = {}
                    elif isinstance(filters, dict):
                        if filters.get("Year") is None:
                            filters.pop("Year", None)

                return item.name, args

    return None

def format_findings(result: ToolResult, question: str = "") -> str:
    """Turn calculation results into readable business answers."""

    if result.error:
        return f"I couldn't complete that calculation: {result.error}"
    
    if result.tool == "get_average_satisfaction":
        return (
            f"The average customer satisfaction score is "
            f"**{result.value:.2f} out of 5**, "
            f"based on {result.rows_used:,} valid survey responses."
        )
    if result.tool == "greatest_store_revenue_decline":
            data = result.value

            decrease = (
                data["previous_revenue"] - data["current_revenue"]
            )

            return (
                f"**Store {data['store_id']}** experienced the greatest "
                f"year-over-year percentage revenue decline, falling "
                f"**{abs(data['percentage_change']):.2f}%** "
                f"from {data['previous_year']} to {data['year']}.\n\n"
                f"Revenue decreased from "
                f"\\${data['previous_revenue']:,.2f} to "
                f"\\${data['current_revenue']:,.2f}, "
                f"a decrease of \\${decrease:,.2f}."
            )
    if result.tool == "greatest_store_revenue_increase":
        data = result.value

        increase = (
            data["current_revenue"] - data["previous_revenue"]
        )

        return (
            f"**Store {data['store_id']}** experienced the greatest "
            f"year-over-year percentage revenue increase, rising "
            f"**{data['percentage_change']:.2f}%** "
            f"from {data['previous_year']} to {data['year']}.\n\n"
            f"Revenue increased from "
            f"\\${data['previous_revenue']:,.2f} to "
            f"\\${data['current_revenue']:,.2f}, "
            f"an increase of \\${increase:,.2f}."
        )
    
    if result.tool == "compare_store_revenue_growth":
        data = result.value

        if data["metric"] == "percentage":
            measurement = "percentage revenue growth"
            growth = f"{data['percentage_change']:.2f}%"
        else:
            measurement = "dollar revenue growth"
            growth = f"\\${data['dollar_change']:,.2f}"

        return (
            f"**Store {data['store_id']}** had the greatest "
            f"{measurement} from {data['start_year']} "
            f"to {data['end_year']}, increasing by **{growth}**.\n\n"
            f"Revenue increased from "
            f"\\${data['start_revenue']:,.2f} to "
            f"\\${data['end_revenue']:,.2f}, "
            f"a total increase of \\${data['dollar_change']:,.2f}."
        )
    
    if result.tool == "get_store_revenue_declines":
        data = result.value
        stores = data["stores"]
      
        if data.get("display_mode") == "summary":
            return data["summary"]
        
        if not stores:
            return (
                f"No stores experienced declining revenue from "
                f"{data['start_year']} to {data['end_year']}."
            )

        lines = [
            f"**{data['declining_store_count']} of "
            f"{data['compared_store_count']} stores** had declining "
            f"revenue from {data['start_year']} to {data['end_year']}.\n",
            "| Store | Starting Revenue | Ending Revenue | Dollar Change | Percentage Change |",
            "|---|---:|---:|---:|---:|"
        ]

        for store in stores:
            lines.append(
                f"| {store['store_id']} "
                f"| \\${store['start_revenue']:,.2f} "
                f"| \\${store['end_revenue']:,.2f} "
                f"| {'-' if store['dollar_change'] < 0 else ''}\\${abs(store['dollar_change']):,.2f} "
                f"| {store['percentage_change']:.2f}% |"
            )

        return "\n".join(lines)
    
    # Format a single revenue result
    if result.tool == "get_total" and isinstance(result.value, (int, float)):
        revenue = f"${result.value:,.2f}"
        filters = result.scope.get("filters")

        if isinstance(filters, dict) and "Year" in filters:
            year = filters["Year"]
            return (
                f"E-Presso generated **{revenue} in revenue in {year}**, "
                f"based on {result.rows_used:,} sales records."
            )

        return (
            f"E-Presso generated **{revenue} in total revenue**, "
            f"based on {result.rows_used:,} sales records."
        )

    # Format revenue by year
    if result.tool == "group_total" and isinstance(result.value, dict):
                # Market comparisons should not be treated as year-over-year growth
        if "Market" in result.definition and result.tool == "group_total":
            if not result.value:
                return "No market revenue data was found for the selected filters."

            ranked_markets = sorted(
                result.value.items(),
                key=lambda item: item[1],
                reverse=True
            )

            question_lower = question.lower()

            asking_lowest = any(
                word in question_lower
                for word in ["least", "lowest", "smallest", "minimum"]
            )

        asking_highest = any(
        word in question_lower
        for word in ["most", "highest", "largest", "maximum", "top"]
        )

        if asking_lowest:
            selected_market, selected_revenue = ranked_markets[-1]
            comparison = "least"
        elif asking_highest:
            selected_market, selected_revenue = ranked_markets[0]
            comparison = "most"
        else:
            selected_market = None
            selected_revenue = None
            comparison = None

            lines = []

            if selected_market is not None:
                lines.append(
                    f"**{selected_market}** generated the {comparison} revenue, "
                    f"with **${selected_revenue:,.2f}**.\n"
                )

            lines.append("**Revenue by market:**")

            for market, revenue in ranked_markets:
                lines.append(f"- **{market}:** ${revenue:,.2f}")

            return "\n".join(lines)
        filters = result.scope.get("filters", {})

        lines = ["E-Presso generated the following revenue each year:\n"]

        for year, revenue in sorted(result.value.items()):
            lines.append(f"- **{year}:** ${revenue:,.2f}")

 # Calculate revenue growth from the first year to the last
        years = sorted(result.value.keys())

        if len(years) >= 2:
            first_year = years[0]
            last_year = years[-1]

            first_revenue = result.value[first_year]
            last_revenue = result.value[last_year]

            if first_revenue > 0:
                growth_result = analytics.calculate_revenue_growth(
                    first_revenue,
                    last_revenue
                )

                growth = growth_result["percentage_change"]
                difference = growth_result["dollar_change"]

                direction = (
                    "increased" if difference >= 0 else "decreased"
                )

                lines.append(
                    f"\n**Key insight:** Revenue {direction} by "
                    f"**${abs(difference):,.2f} ({abs(growth):.1f}%)** "
                    f"from {first_year} to {last_year}."
                )

        return "\n".join(lines)
    # Format data-quality results
    if result.tool == "data_quality_report" and isinstance(result.value, dict):
        rows = result.value.get("rows", 0)
        duplicates = result.value.get("duplicate_rows", 0)
        missing = result.value.get("columns_with_missing", {})

        lines = [
            f"I reviewed **{rows:,} records** for missing values "
            f"and completely duplicate rows.",
            ""
        ]

        if duplicates == 0:
            lines.append("**Duplicate rows:** None found.")
        else:
            lines.append(
                f"**Duplicate rows:** {duplicates:,} found."
            )

        if not missing:
            lines.append("**Missing values:** None found.")
        else:
            lines.append("**Missing values by column:**")
            for column, count in missing.items():
                lines.append(f"- {column}: {count:,}")

        lines.append(
            "\n**What this means:** These checks help identify "
            "potential data-quality issues, but they do not "
            "guarantee that every record is accurate."
        )

        return "\n\n".join(lines)

    # Keep other analytical results unchanged for now
    return f"{result.definition}: {result.value} (rows used: {result.rows_used})"


def answer_question(
    question: str,
    df,
    mode: str = 'rules',
    survey_df=None
) -> dict:
    log = []

    routed = (
        rules_router(question, df)
        if mode == 'rules'
        else llm_router(question, df)
    )

    if routed is None:
        return {
            'scope': 'Selected dataset; no calculation performed',
            'findings': UNSUPPORTED,
            'interpretation': (
                'The current analytical tools cannot reliably '
                'answer this question.'
            ),
            'next_steps': (
                'Try asking about total revenue, revenue by year, '
                'year comparisons, or missing and duplicate data.'
            ),
            'tool_log': log
        }

    name, args = routed
    result = run_tool(name, args, df, log, survey_df=survey_df)

    # Choose summary or full table for revenue-decline questions
    if name == "get_store_revenue_declines" and not result.error:
        question_lower = question.lower()

        if any(word in question_lower for word in [
            "summarize", "summary", "overview", "brief"
        ]):
            data = result.value
            stores = data["stores"]

            if stores:
                worst = stores[0]

                result.value["display_mode"] = "summary"
                result.value["summary"] = (
                    f"{data['declining_store_count']} of "
                    f"{data['compared_store_count']} stores had "
                    f"declining revenue from {data['start_year']} "
                    f"to {data['end_year']}. "
                    f"Store {worst['store_id']} had the largest "
                    f"percentage decline at "
                    f"{worst['percentage_change']:.2f}%, "
                    f"equivalent to a dollar change of "
                    f"{'-' if worst['dollar_change'] < 0 else ''}\\${abs(worst['dollar_change']):,.2f}."
                )
            else:
                result.value["display_mode"] = "summary"
                result.value["summary"] = (
                    "No stores experienced declining revenue "
                    "during the selected period."
                )
        else:
            result.value["display_mode"] = "table"


       # Create a readable description of the calculation scope
    filters = result.scope.get('filters', 'All records')

    if isinstance(filters, dict):
        if filters:
            scope_text = ', '.join(
                f"{key}: {value}"
                for key, value in filters.items()
            )
        else:
            scope_text = 'All records'
    elif isinstance(filters, str):
        scope_text = filters if filters.strip() else 'All records'
    else:
        scope_text = 'All records'

    # Recommend further investigation without claiming a cause
    if result.error:
        next_steps = (
            'Check the requested filters and available data, '
            'then try again.'
        )
    elif name in ('get_total', 'group_total'):
        next_steps = (
            'Compare revenue across other years or groups '
            'to investigate differences in performance.'
        )
    elif name == 'data_quality_report':
        next_steps = (
            'Review unique record identifiers and other '
            'data validation checks for additional issues.'
        )
    else:
        next_steps = 'No recommendation is supported by this data.'

    return {
        'scope': scope_text,
        'findings': format_findings(result, question),
        'interpretation': ' '.join(result.caveats),
        'next_steps': next_steps,
        'tool_log': log
    }
