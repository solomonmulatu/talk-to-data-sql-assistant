from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncConnection

from introspection.prompts import SQL_SYSTEM_PROMPT, SCHEMA_TEXT_PROMPT
from src.talk_to_data.config import settings


class SqlGenerator:

    def __init__(self ):
        self.llm = ChatOpenAI(
            model=settings.openai_chat_model,
            temperature=0,
        )




    async def generate_sql(self
,question: str):


        response = await self.llm.ainvoke([
            SystemMessage(content=SQL_SYSTEM_PROMPT),
            HumanMessage(content=f"""Question: {question}""")
        ]
        )

        sql = response.content.strip()

        if sql == "WRITE_REQUEST":
            return {"result":"ERROR","message": "This app is read-only, so it cannot delete or change data."}

        if sql == "UNANSWERABLE":
            return {"result":"ERROR","message": "That question cannot be answered from this database."}

        return{
            "result":"SUCCESS",
            "sql":sql,
        }









    async def repair_sql(
            self,
            question: str,
            failed_sql: str,
            error: str,
    ) -> str:
        response = await self.llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You generate PostgreSQL SELECT queries. "
                        "Correct the failed query using the supplied schema and error. "
                        "Return only one SQL SELECT query, with no Markdown fences. "
                        "Do not use INSERT, UPDATE, DELETE, DROP, or other write commands. "
                        "Do not invent tables or columns."
                    )
                ),
                HumanMessage(
                    content=f"""
    Question:
    {question}

    Database schema:
    {SCHEMA_TEXT_PROMPT}

    Failed SQL:
    {failed_sql}

    Database or validation error:
    {error[:1500]}
    """
                ),
            ]
        )

        repaired_sql = response.content.strip()

        if not repaired_sql:
            raise ValueError("The model returned an empty SQL repair.")

        return repaired_sql

