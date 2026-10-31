from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from introspection.prompts import ALLOWED_TABLES
from introspection.sql_generator import SqlGenerator
from introspection.validator import UnsafeQueryError, Validator


class QueryFailedError(Exception):
    pass


class Executor:
    def __init__(self):
        pass

    validator = Validator()

    async def execute_query(
            self,
            connection: AsyncConnection,
            sql: str,
            allowed_tables: set[str]=ALLOWED_TABLES,
    ) -> dict:

        print("inside executor sql....")


        """Validate and run one read-only query. Raises on any failure."""
        safe_sql = self.validator.validate_sql(sql, allowed_tables)

        # Start from a clean transaction state.
        await connection.rollback()

        try:

            result = await connection.exec_driver_sql(safe_sql)
            rows = [dict(row) for row in result.mappings().all()]
        finally:
            # Always end the transaction so the connection goes back clean,
            # on success as well as on failure.
            await connection.rollback()

        return {"sql": safe_sql, "rows": rows}

    async def execute_with_repair(
            self,
            connection: AsyncConnection,
            question: str,
            sql: str,
            allowed_tables: set[str] = ALLOWED_TABLES,
            max_retries: int = 2,
    ) -> dict:
        current_sql = sql
        generator = SqlGenerator()

        for attempt in range(max_retries + 1):
            try:
                result = await self.execute_query(connection, current_sql, allowed_tables)
                result["retries"] = attempt
                return result

            except (UnsafeQueryError, DBAPIError) as exc:
                if attempt == max_retries:
                    raise QueryFailedError(
                        "I couldn't produce a valid query for that question."
                    ) from exc

                current_sql = await generator.repair_sql(
                    question=question,
                    failed_sql=current_sql,
                    error=str(exc),
                )
