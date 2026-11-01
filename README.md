# Talk to Data

Ask questions about a PostgreSQL database in plain English. The application uses an LLM to draft a SQL query, validates it, runs it against a read-only database connection, and returns a short summary grounded in the result rows, optional Plotly chart JSON, and the result data. A Streamlit UI talks to the FastAPI service and shows the summary, table, and chart.

> **Project status:** early development. This README and [docs/DESIGN.MD](docs/DESIGN.MD) both describe the current implementation.

## What it does

- Converts a natural-language question into a SQL `SELECT` query with LangChain and OpenAI (`ChatOpenAI`).
- Supplies schema context from a **fixed Chinook-style schema string** in `introspection/prompts.py` (not live PostgreSQL introspection yet).
- Validates generated SQL with `sqlglot` before execution: one `SELECT`, allowed tables, and a row `LIMIT`.
- Executes validated SQL on a connection with `default_transaction_read_only` and a statement timeout.
- Asks the LLM for a grounded summary and chart configuration, then builds a Plotly figure when visualization is useful.
- Serves results over `POST /query`; Streamlit displays summary, result rows, and chart (it does not show the generated SQL yet).
- Runs a lightweight API contract evaluation over curated questions in `eval/`.

## Example questions

Using a Chinook-compatible sample database (lowercase snake_case table and column names matching the embedded schema), you could ask:

- Which artists have the most tracks?
- What were total sales by country?
- Which customers spent the most?
- How many invoices were created each month?

## Architecture

```mermaid
flowchart LR
    Q[Question] --> UI[Streamlit UI]
    UI -->|"POST /query"| API[FastAPI]
    API --> L[LLM generates SQL]
    L --> V[Validate: SELECT only, allowlist, LIMIT]
    V --> E[Execute read-only connection]
    E --> R[Result rows]
    R --> S[LLM summary and chart config]
    S --> C[Plotly chart builder]
    S --> O[API response]
    C --> O
    O --> UI
```

Stack: PostgreSQL, SQLAlchemy 2 (async) and Psycopg 3, LangChain with `langchain-openai`, FastAPI, Streamlit, sqlglot, pandas, and Plotly.

### API shape

`POST /query` with query parameter `query` (the natural-language question).

Success response:

```json
{
  "summary": "…",
  "chart": "{…plotly figure json…} or null",
  "data": [{"column": "value"}]
}
```

Unanswerable or write-style questions return something like:

```json
{
  "result": "ERROR",
  "message": "That question cannot be answered from this database."
}
```

## Requirements

- Python 3.14 or newer (see `requires-python` in `pyproject.toml`)
- PostgreSQL installed and running locally, or access to a PostgreSQL server
- [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management
- An OpenAI API key for the configured model

## Quickstart

### 1. Clone the repository

```powershell
git clone <your-repository-url>
cd talk-to-data
```

### 2. Create a local PostgreSQL database

In `psql` or pgAdmin, create a database and an application user. For local development, you can run:

```sql
CREATE USER talk_to_data WITH PASSWORD 'change_this_local_password';
CREATE DATABASE talk_to_data OWNER talk_to_data;
```

Do not use these development credentials in a deployed environment. Prefer a dedicated read-only role for query execution when you harden the setup.

### 3. Install the Python dependencies

```powershell
uv sync
```

### 4. Configure environment variables

Copy the example file and edit it:

```powershell
Copy-Item .env.example .env
```

Set at least:

```env
DATABASE_URL=postgresql+psycopg://talk_to_data:change_this_local_password@localhost:5432/talk_to_data
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_CHAT_MODEL=gpt-4o
```

`config.py` reads `OPENAI_CHAT_MODEL` (default `gpt-4o`). If `.env.example` still shows `OPENAI_MODEL`, use that value as `OPENAI_CHAT_MODEL` in `.env`.

Never commit `.env` or API keys.

### 5. Load the Chinook sample data (optional)

Download a PostgreSQL SQL script from the [Chinook database releases](https://github.com/lerocha/chinook-database/releases), then import it into your `talk_to_data` database. From PowerShell, if `psql` is on your PATH:

```powershell
psql -h localhost -U talk_to_data -d talk_to_data -f .\Chinook_PostgreSql.sql
```

The prompts and allowlist currently assume **lowercase snake_case** Chinook-like names (`album`, `artist`, `invoice`, …). If your dump uses quoted PascalCase identifiers, rename objects or update `introspection/prompts.py` so names match. Check Chinook’s license and attribution before redistributing its data with this project.

### 6. Start the API and UI

From the repository root (imports use both `introspection` and `src.talk_to_data`):

```powershell
uv run uvicorn src.talk_to_data.api:app --reload
```

In another window:

```powershell
uv run streamlit run app/streamlit_app.py
```

Open the local Streamlit URL printed in the terminal. FastAPI docs are at `http://127.0.0.1:8000/docs`.

## Safety

Generated SQL is untrusted input. The current code:

- Sets the session to read-only and applies a PostgreSQL `statement_timeout` (5s) on the app connection.
- Parses SQL with `sqlglot` and allows only one `SELECT` (including CTEs / unions as queries).
- Rejects DML, DDL, and other blocked constructs.
- Checks referenced tables against a fixed allowlist derived from the embedded schema.
- Enforces a maximum row count (`LIMIT`) when missing or too large.

SQL validation is defense in depth, not a substitute for database permissions. Prefer an execution role without `INSERT`, `UPDATE`, `DELETE`, DDL, or admin privileges.

An `execute_with_repair` path exists in the executor but is **not** used by the `/query` API yet.

## Evaluation

`eval/run_eval.py` posts each case in `eval/questions.json` to `POST /query` and checks response shape: non-empty `summary`, list `data`, expected chart type when applicable, and rejection of unanswerable cases. It does **not** yet compare generated query results to reference SQL.

```powershell
uv run python eval/run_eval.py
```

Optional flags: `--url`, `--questions`, `--timeout`, `--limit`, `--report`.

| Experiment | Contract pass rate | Notes |
|---|---:|--- |
| To be measured | — | Fill in after running the eval runner against a loaded Chinook DB. |

## Project structure

```text
talk-to-data/
├── src/talk_to_data/
│   ├── config.py          # Settings from .env
│   ├── db.py              # Async engine, read-only connection, timeout
│   ├── api.py             # FastAPI POST /query orchestration
│   ├── executor.py        # Validate + execute (repair helper unused by API)
│   ├── charts.py          # Plotly chart builders
│   └── summarizer.py      # LLM summary + chart config
├── introspection/
│   ├── prompts.py         # Embedded schema, allowlist, SQL/summary prompts
│   ├── sql_generator.py   # NL → SQL (and repair helper)
│   └── validator.py       # sqlglot SELECT / allowlist / LIMIT checks
├── app/
│   └── streamlit_app.py   # UI: summary, table, chart
├── eval/
│   ├── questions.json     # Curated questions and expected chart hints
│   └── run_eval.py        # API contract / smoke evaluation
├── data/                  # Optional local sample data (not committed dumps)
├── scripts/               # Placeholders for setup helpers
├── tests/                 # Not populated yet
├── docs/
│   └── DESIGN.MD          # Current architecture notes
├── .env.example
├── pyproject.toml
├── uv.lock
├── LICENSE
└── README.md
```

## Limitations and future work

- Schema context is hardcoded for a Chinook-like model; live Postgres introspection is not implemented.
- The UI does not display the generated SQL; the API response does not include it.
- Chart choice is LLM-driven (with a Streamlit fallback from rows), not a separate deterministic selector in the API.
- SQL repair on validation/DB errors is implemented but not wired into `/query`.
- Evaluation is contract/smoke style, not execution-accuracy against reference SQL.
- `tests/`, download helpers under `scripts/`, and a filled changelog are incomplete.
- PostgreSQL only; single-user; no auth. Possible later work includes schema selection, CSV upload, conversation memory, and a semantic layer.

## Development

Automated lint/test tooling is not configured in `pyproject.toml` yet. When you add them, prefer covering the SQL validator, chart builders, and a mocked end-to-end `/query` path.

Architecture details live in [docs/DESIGN.MD](docs/DESIGN.MD).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). Review the Chinook dataset’s license and attribution requirements separately before including its data or scripts in a distribution.

## Acknowledgements

- [Chinook sample database](https://github.com/lerocha/chinook-database)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Psycopg](https://www.psycopg.org/)
- [LangChain](https://www.langchain.com/)
- [Streamlit](https://streamlit.io/)
