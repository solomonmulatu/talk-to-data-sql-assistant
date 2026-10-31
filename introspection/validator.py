import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from introspection.prompts import ALLOWED_TABLES


class UnsafeQueryError(ValueError):
    pass


class Validator:
    def __init__(self):
        pass

    def validate_sql(
            self,
            sql: str,
            allowed_tables: set[str]=ALLOWED_TABLES,
            max_rows: int = 1000,
    ) -> str:

        print("inside validate sql....")
        # Accept a fenced SQL answer from the model, if it returns one.
        sql = sql.strip().removeprefix("```sql").removesuffix("```").strip()

        try:
            statements = [stmt for stmt in sqlglot.parse(sql, read="postgres") if stmt]
        except ParseError as exc:
            raise UnsafeQueryError("Could not parse the generated SQL.") from exc

        if len(statements) != 1:
            raise UnsafeQueryError("Only one SQL statement is allowed.")

        query = statements[0]

        # A SELECT (including a SELECT with CTEs or UNION) is a Query in SQLGlot.
        if not isinstance(query, exp.Query):
            raise UnsafeQueryError("Only SELECT queries are allowed.")

        # Block data changes, DDL, unparsed commands, and SELECT INTO.
        if any(
                isinstance(node, (exp.DML, exp.DDL, exp.Command, exp.Into))
                for node in query.walk()
        ):
            raise UnsafeQueryError("The query contains a blocked operation.")

        # Allow references to CTE names, but only approved real tables.
        cte_names = {
            cte.alias_or_name.lower()
            for cte in query.find_all(exp.CTE)
        }

        for table in query.find_all(exp.Table):
            table_name = table.name.lower()

            if table_name in cte_names:
                continue

            if table_name not in {name.lower() for name in allowed_tables}:
                raise UnsafeQueryError(f"Table is not allowed: {table.name}")

            if table.db and table.db.lower() != "public":
                raise UnsafeQueryError("Only tables in the public schema are allowed.")

        # Add a row limit if missing; cap a larger numeric LIMIT.
        limit = query.args.get("limit")
        if limit is None:
            query = query.limit(max_rows, copy=False)
        else:
            limit_value = limit.expression
            if not isinstance(limit_value, exp.Literal) or limit_value.is_string:
                raise UnsafeQueryError("Use a simple numeric LIMIT.")
            try:
                requested_rows = int(limit_value.this)
            except (TypeError, ValueError) as exc:
                raise UnsafeQueryError("Use a simple numeric LIMIT.") from exc

            if requested_rows < 0:
                raise UnsafeQueryError("LIMIT cannot be negative.")
            if requested_rows > max_rows:
                limit.set("expression", exp.Literal.number(max_rows))

        return query.sql(dialect="postgres")





