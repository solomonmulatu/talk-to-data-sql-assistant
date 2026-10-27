# Talk to Data

Ask questions about a PostgreSQL database in plain English. The application uses an LLM to draft a SQL query, validates it, runs it against a read-only database connection, and returns the SQL, results, an appropriate chart, and a short summary grounded in those results.

> **Project status:** early development. Architecture, setup, evaluation results, and demo links will be updated as features are completed.

## What it does

- Inspects PostgreSQL tables, columns, types, and relationships to give the model relevant schema context.
- Converts a natural-language question into a SQL `SELECT` query.
- Validates generated SQL before execution and limits returned rows.
- Displays the generated SQL, result table, chart (when useful), and a concise summary.
- Evaluates generated queries against a curated set of questions and reference SQL.

## Example questions

Using the Chinook sample database, you could ask:

- Which artists have the most tracks?
- What were total sales by country?
- Which customers spent the most?
- How many invoices were created each month?

## Architecture

```mermaid
flowchart LR
    Q[Question] --> S[Inspect PostgreSQL schema]
    S --> L[LLM generates SQL]
    L --> V[Validate: SELECT only, allowed tables, row limit]
    V --> E[Execute with read-only database role]
    E --> R[Result rows]
    R --> C[Choose table or chart]
    R --> U[LLM summary grounded in results]
    C --> O[API and Streamlit UI]
    U --> O
```

The database layer uses PostgreSQL, SQLAlchemy 2, and Psycopg 3. LangChain structures the LLM workflow, and its `langchain-openai` integration connects to OpenAI models. FastAPI provides the API and Streamlit provides the user interface.

## Requirements

- Python 3.11 or newer
- PostgreSQL installed and running locally, or access to a PostgreSQL server
- [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management
- An API key for the configured LLM provider, if using a hosted model

## Quickstart

### 1. Clone the repository

```powershell
git clone <your-repository-url>
cd talk-to-data-sql-assistant
```

### 2. Create a local PostgreSQL database

In `psql` or pgAdmin, create a database and an application user. For local development, you can run:

```sql
CREATE USER talk_to_data WITH PASSWORD 'change_this_local_password';
CREATE DATABASE talk_to_data OWNER talk_to_data;
```

Do not use these development credentials in a deployed environment. For production, configure a dedicated read-only role for query execution.

### 3. Install the Python dependencies

```powershell
uv sync
```

If the project does not yet include a lockfile, create the environment and install dependencies with:

```powershell
uv venv
uv add fastapi "uvicorn[standard]" sqlalchemy "psycopg[binary]" python-dotenv pandas plotly sqlglot streamlit langchain langchain-openai
```

### 4. Configure environment variables

Copy the example file and edit it:

```powershell
Copy-Item .env.example .env
```

Set at least the database URL in `.env`:

```env
DATABASE_URL=postgresql+psycopg://talk_to_data:change_this_local_password@localhost:5432/talk_to_data
```

Add provider-specific settings when configuring the LLM, for example:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=your-selected-model
```

Use `ChatOpenAI` from the `langchain-openai` integration in your LLM module. In FastAPI async routes, call `await model.ainvoke(...)`. Set `OPENAI_API_KEY` and your chosen model name in `.env`. See the [LangChain ChatOpenAI integration guide](https://docs.langchain.com/oss/python/integrations/chat/openai) for current setup and usage.

Never commit `.env` or API keys. `.env.example` should contain variable names and safe placeholder values only.

### 5. Load the Chinook sample data (optional)

Download the PostgreSQL SQL script from the [Chinook database releases](https://github.com/lerocha/chinook-database/releases), then import it into your `talk_to_data` database. From PowerShell, if `psql` is on your PATH:

```powershell
psql -h localhost -U talk_to_data -d talk_to_data -f .\Chinook_PostgreSql.sql
```

The Chinook repository provides a PostgreSQL version of its sample database script. Check its license and attribution terms before redistributing the data file with this project. [Chinook database](https://github.com/lerocha/chinook-database)

### 6. Start the API and UI

The commands below assume the API entry point will be `src/talk_to_data/api.py` and the Streamlit entry point will be `app/streamlit_app.py`; adjust them if the repo layout changes.

In one PowerShell window:

```powershell
uv run uvicorn talk_to_data.api:app --app-dir src --reload
```

In another:

```powershell
uv run streamlit run app/streamlit_app.py
```

Open the local Streamlit URL printed in the terminal. FastAPI’s interactive API documentation will be available at `http://127.0.0.1:8000/docs`.

## Safety

Generated SQL is untrusted input. The application is designed to:

- Use a PostgreSQL role with read-only permissions for query execution.
- Parse and validate each query, allowing only one `SELECT` statement.
- Reject modifying statements and unsupported SQL constructs.
- Check referenced tables against the inspected schema.
- Enforce a maximum result size and a query timeout.
- Avoid interpolating user-provided values into SQL strings.

SQL validation is an additional guard, not a replacement for database permissions. The execution role should not have `INSERT`, `UPDATE`, `DELETE`, DDL, or administrative privileges.

## Evaluation

Evaluation compares generated query results with reference-query results rather than requiring identical SQL text. Planned metrics include execution accuracy, query validity, repair rate, and latency.

| Experiment | Execution accuracy | Valid query rate | Notes |
|---|---:|---:|---|
| To be measured | — | — | Add results after running `eval/run_eval.py`. |

## Project structure

```text
src/talk_to_data/
├── config.py          # Application settings
├── db.py              # PostgreSQL connection and schema inspection
├── prompts.py         # LLM instructions and examples
├── sql_generator.py   # Natural language to SQL
├── validator.py       # SQL parsing and safety checks
├── executor.py        # Read-only query execution
├── charts.py          # Chart selection and construction
├── summarizer.py      # Summary grounded in query results
└── api.py             # FastAPI endpoints
app/
└── streamlit_app.py   # Streamlit user interface
data/                  # Optional local sample data; do not commit secrets
scripts/               # Data setup or download helpers
eval/                  # Evaluation questions and runner
tests/                 # Automated tests
docs/                  # Design notes and architecture documentation
```

## Limitations and future work

- PostgreSQL is the supported database dialect.
- Query quality depends on the schema context and the selected LLM.
- Ambiguous or unsupported questions should receive a clear explanation instead of a guessed answer.
- Authentication, multi-user access, and database-dialect portability are outside the initial scope.
- Future work may include schema selection for large databases, CSV uploads, conversation memory, and a semantic layer.

## Development

Run linting and tests (once configured in the repository):

```powershell
uv run ruff check .
uv run pytest
```

Prioritize tests for the SQL validator, chart selection, and an end-to-end flow using a small test database. Mock LLM calls in automated tests.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). Review the Chinook dataset’s license and attribution requirements separately before including its data or scripts in a distribution.

## Acknowledgements

- [Chinook sample database](https://github.com/lerocha/chinook-database)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Psycopg](https://www.psycopg.org/)



