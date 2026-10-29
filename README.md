# E-Presso BI Analyst

The app is being built in checkpoints. The current checkpoint loads and profiles
the E-Presso sources independently; it does not join tables or calculate revenue.

## What this application does
_To be completed as the dashboard is built._

## Live app
_Add the deployed app URL._

## How to use it
Upload all three source files in the sidebar:

- The sales workbook, with `Sales`, `Products`, and `Categories` sheets.
- The tab-delimited stores file.
- The survey workbook, with a `Survey Results` sheet whose column headers begin
  on the third row.

The app displays each table separately, including a preview, missing values,
data types, duplicate rows, and a candidate grain-key check. No tables are
joined at this stage.

## Data model
Current grain statements and candidate keys:

| Table | Grain statement | Candidate key |
|---|---|---|
| Sales | One row per store, date, and product combination | `Date`, `Store ID`, `Product ID` |
| Products | One row per product | `Product ID` |
| Categories | One row per product category | `Category ID` |
| Stores | One row per store or sales channel | `ID` |
| Survey Results | One row per store and survey year | `Store ID`, `Year` |

These are based on the provided files and should be confirmed against the
assignment's data definitions. Joins and merge checks have not been performed.

## Metric definitions
Revenue has not yet been calculated. The next checkpoint is to calculate one
total and reconcile it with Power BI. Revenue is not profit.

## Assistant
Not part of the current checkpoint.

## Validation
Source profiling and grain-key checks are covered by the test suite. Power BI
reconciliation and the $1,000 test are still pending.

## Limitations
The app currently profiles source tables only. It cannot yet report revenue,
profit, trends, or customer-satisfaction findings.

## Files
| File | Purpose |
|---|---|
| `streamlit_app.py` | Screen layout and interaction |
| `analytics.py` | Metrics and analytical functions (no Streamlit code) |
| `agent.py` | Assistant tools and routing (later checkpoint) |
| `tests/` | Tests with hand-checkable answers |
| `requirements.txt` | Packages the hosted app needs |

## Run it
Hosted: deploy from this repository on share.streamlit.io with main file `streamlit_app.py`.

Locally (optional): `pip install -r requirements-dev.txt`, then `streamlit run streamlit_app.py`. Run tests with `pytest`.

## Secrets
Never commit API keys. Use Streamlit Secrets (see `.streamlit/secrets.toml.example`).
