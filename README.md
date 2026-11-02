# Talk to Data

Ask questions about a PostgreSQL database in plain English. The application uses an LLM to draft a SQL query, validates it, runs it against a read-only database connection, and returns the final SQL, a short summary grounded in the result rows, optional Plotly chart JSON, and the result data. A Streamlit UI talks to the FastAPI service and shows the summary, generated SQL, table, and chart.

> **Project status:** early development. This README and [docs/DESIGN.MD](docs/DESIGN.MD) both describe the current implementation.

## What it does

- Converts a natural-language question into a SQL `SELECT` query with LangChain and OpenAI (`ChatOpenAI`).
- Supplies schema context from a **fixed Chinook-style schema string** in `introspection/prompts.py` (not live PostgreSQL introspection yet).
- Validates generated SQL with `sqlglot` before execution: one `SELECT`, allowed tables, and a row `LIMIT`.
- Executes validated SQL on a connection with `default_transaction_read_only` and a statement timeout.
- On validation or database errors, runs one bounded SQL repair through the LLM and re-validates before retrying.
- Asks the LLM for a grounded summary and chart configuration, then builds a Plotly figure when visualization is useful.
- Serves results over `POST /ask`; Streamlit displays summary, generated SQL, result rows, and chart.
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
    UI -->|"POST /ask"| API[FastAPI]
    API --> L[LLM generates SQL]
    L --> V[Validate: SELECT only, allowlist, LIMIT]
    V --> E[Execute read-only connection]
    E -->|validation or DB error| Rpr[One LLM SQL repair]
    Rpr --> V
    E --> R[Result rows]
    R --> S[LLM summary and chart config]
    S --> C[Plotly chart builder]
    S --> O[API response]
    C --> O
    O --> UI
```

Stack: PostgreSQL, SQLAlchemy 2 (async) and Psycopg 3, LangChain with `langchain-openai`, FastAPI, Streamlit, sqlglot, pandas, and Plotly.

### API shape

`POST /ask` with query parameter `question` (the natural-language question).

Success response:

```json
{
  "summary": "...",
  "sql": "SELECT ... LIMIT 1000",
  "chart": "{...plotly figure json...} or null",
  "data": [{"column": "value"}],
  "retries": 0
}
```

`sql` is the final validated statement that ran (including any repair and enforced `LIMIT`). `retries` is `0` when the first SQL succeeds, or `1` when a single repair attempt was used.

Unanswerable, write-style, or unrecoverable query failures return something like:

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
git clone https://github.com/solomonmulatu/talk-to-data-sql-assistant
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

`config.py` reads `OPENAI_CHAT_MODEL` (default `gpt-4o`). `postgres://` and `postgresql://` database URLs are normalized to `postgresql+psycopg://`. Supabase hosts also get `sslmode=require` when it is missing.

For Streamlit against a remote API, set `API_URL` to the full ask endpoint (for example `https://your-api.onrender.com/ask`). If unset, Streamlit uses `API_BASE_URL` + `/ask`, defaulting to `http://localhost:8000/ask`.

Never commit `.env` or API keys.

### 5. Load the Chinook sample data (optional)

Download a PostgreSQL SQL script from the [Chinook database releases](https://github.com/lerocha/chinook-database/releases), then import it into your `talk_to_data` database. From PowerShell, if `psql` is on your PATH:

```powershell
psql -h localhost -U talk_to_data -d talk_to_data -f .\Chinook_PostgreSql.sql
```

The prompts and allowlist currently assume **lowercase snake_case** Chinook-like names (`album`, `artist`, `invoice`, â€¦). If your dump uses quoted PascalCase identifiers, rename objects or update `introspection/prompts.py` so names match. Check Chinookâ€™s license and attribution before redistributing its data with this project.

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

If the first SQL fails validation or execution, `/ask` asks the model for one corrected `SELECT`, runs that candidate through the same validator, and records how many repair attempts were used in `retries`.

## Evaluation

`eval/run_eval.py` posts each case in `eval/questions.json` to `POST /ask` and checks response shape: non-empty `summary`, list `data`, expected chart type when applicable, and rejection of unanswerable cases. It does **not** yet compare generated query results to reference SQL.

```powershell
uv run python eval/run_eval.py
```

Optional flags: `--url`, `--questions`, `--timeout`, `--limit`, `--report`.

| Experiment | Contract pass rate | Notes |
|---|---:|--- |
| To be measured | â€” | Fill in after running the eval runner against a loaded Chinook DB. |

## Project structure

```text
talk-to-data/
â”œâ”€â”€ src/talk_to_data/
â”‚   â”œâ”€â”€ config.py          # Settings from .env
â”‚   â”œâ”€â”€ db.py              # Async engine, read-only connection, timeout
â”‚   â”œâ”€â”€ api.py             # FastAPI POST /ask orchestration
â”‚   â”œâ”€â”€ executor.py        # Validate + execute with one bounded repair
â”‚   â”œâ”€â”€ charts.py          # Plotly chart builders
â”‚   â””â”€â”€ summarizer.py      # LLM summary + chart config
â”œâ”€â”€ introspection/
â”‚   â”œâ”€â”€ prompts.py         # Embedded schema, allowlist, SQL/summary prompts
â”‚   â”œâ”€â”€ sql_generator.py   # NL â†’ SQL and repair_sql
â”‚   â””â”€â”€ validator.py       # sqlglot SELECT / allowlist / LIMIT checks
â”œâ”€â”€ app/
â”‚   â””â”€â”€ streamlit_app.py   # UI: summary, SQL, table, chart
â”œâ”€â”€ eval/
â”‚   â”œâ”€â”€ questions.json     # Curated questions and expected chart hints
â”‚   â””â”€â”€ run_eval.py        # API contract / smoke evaluation
â”œâ”€â”€ data/                  # Optional local sample data (not committed dumps)
â”œâ”€â”€ scripts/               # Placeholders for setup helpers
â”œâ”€â”€ tests/                 # Not populated yet
â”œâ”€â”€ docs/
â”‚   â””â”€â”€ DESIGN.MD          # Current architecture notes
â”œâ”€â”€ .env.example
â”œâ”€â”€ pyproject.toml
â”œâ”€â”€ uv.lock
â”œâ”€â”€ LICENSE
â””â”€â”€ README.md
```

## Deploy (Render + Supabase)

Use **Supabase** for PostgreSQL and **Render** for the app (two web services: API and Streamlit).

1. Create a Supabase project and import Chinook with **lowercase snake_case** table/column names matching `introspection/prompts.py`.
2. Copy the Supabase database URI into the API service as `DATABASE_URL` (scheme `postgres://` / `postgresql://` is fine; the app rewrites it for Psycopg and adds SSL for Supabase hosts). Prefer a read-only DB user when you harden the setup.
3. Create a Render **API** web service from this repo:
   - Build: `pip install .` or `uv sync --frozen` (ensure the Render Python version satisfies `requires-python` in `pyproject.toml`)
   - Start: `uvicorn src.talk_to_data.api:app --host 0.0.0.0 --port $PORT`
   - Env: `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, `DATABASE_URL`
4. Create a Render **Streamlit** web service from the same repo:
   - Start: `streamlit run app/streamlit_app.py --server.port $PORT --server.address 0.0.0.0`
   - Env: `API_URL=https://<your-api-service>.onrender.com/ask`
5. Open the Streamlit URL and ask a Chinook question.

Free Render instances sleep when idle; the first request after idle can be slow.

## Limitations and future work

- Schema context is hardcoded for a Chinook-like model; live Postgres introspection is not implemented.
- Chart choice is LLM-driven (with a Streamlit fallback from rows), not a separate deterministic selector in the API.
- Evaluation is contract/smoke style, not execution-accuracy against reference SQL.
- `tests/`, download helpers under `scripts/`, and a filled changelog are incomplete.
- PostgreSQL only; single-user; no auth. Possible later work includes schema selection, CSV upload, conversation memory, and a semantic layer.

## Development

Automated lint/test tooling is not configured in `pyproject.toml` yet. When you add them, prefer covering the SQL validator, chart builders, and a mocked end-to-end `/ask` path.

Architecture details live in [docs/DESIGN.MD](docs/DESIGN.MD).

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). Review the Chinook datasetâ€™s license and attribution requirements separately before including its data or scripts in a distribution.

## Acknowledgements

- [Chinook sample database](https://github.com/lerocha/chinook-database)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Psycopg](https://www.psycopg.org/)
- [LangChain](https://www.langchain.com/)
- [Streamlit](https://streamlit.io/)
