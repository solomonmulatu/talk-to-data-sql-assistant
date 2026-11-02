from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncConnection

from introspection.sql_generator import SqlGenerator
from src.talk_to_data.charts import ChartGenerator
from src.talk_to_data.db import get_connection
from src.talk_to_data.executor import Executor, QueryFailedError
from src.talk_to_data.summarizer import Summarizer

app = FastAPI()

ConnectionDep = Annotated[AsyncConnection, Depends(get_connection)]

generator = SqlGenerator()
executor = Executor()
summarizer = Summarizer()
chart_generator = ChartGenerator()


@app.post("/query")
async def root(connection: ConnectionDep, query: str):
    question = query

    response = await generator.generate_sql(question=question)

    if response["result"] != "SUCCESS":
        return response

    try:
        sql_result = await executor.execute_with_repair(
            connection,
            question=question,
            sql=response["sql"],
            max_retries=1,
        )

        df = pd.DataFrame(sql_result["rows"])
        analysis = summarizer.analyze(question=question, df=df)

        chart = None
        if analysis.chart.should_visualize:
            chart = chart_generator.generate_chart(
                df=df,
                chart_type=analysis.chart.chart_type,
                x=analysis.chart.x,
                y=analysis.chart.y,
                title=analysis.chart.title,
            )

        return {
            "summary": analysis.summary,
            "chart": chart.to_json() if chart else None,
            "data": df.to_dict(orient="records"),
            "retries": sql_result.get("retries", 0),
        }

    except QueryFailedError as e:
        return {"result": "ERROR", "message": str(e)}
