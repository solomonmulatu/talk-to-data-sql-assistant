import asyncio
from typing import Annotated

import pandas as pd
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from introspection.sql_generator import SqlGenerator
from introspection.validator import Validator, UnsafeQueryError
from src.talk_to_data.charts import ChartGenerator
from src.talk_to_data.db import get_connection
from src.talk_to_data.executor import Executor
from src.talk_to_data.summarizer import Summarizer

app = FastAPI()

ConnectionDep = Annotated[AsyncConnection, Depends(get_connection)]

generator=SqlGenerator()
executor=Executor()
summarizer=Summarizer()
chart_generator=ChartGenerator()
@app.post("/query")
async def root(connection: ConnectionDep,query: str ):

    question=query


    response=await generator.generate_sql(question=question)
    print(f"summarized_result is \n{response}")

    if response["result"]=="SUCCESS":
        try:
            sql_result = await executor.execute_query(connection, response["sql"])
            print(f"result is \n{sql_result}")

            df = pd.DataFrame(sql_result["rows"])
            analysis=summarizer.analyze(question=question,df=df)

            chart = None

            if analysis.chart.should_visualize:
                chart = chart_generator.generate_chart(
                    df=df,
                    chart_type=analysis.chart.chart_type,
                    x=analysis.chart.x,
                    y=analysis.chart.y,
                    title=analysis.chart.title
                )
            print(f"summarized_result is \n{analysis}")

            return {
                "summary": analysis.summary,
                "chart": chart.to_json() if chart else None,
                "data": df.to_dict(orient="records")
            }




        except UnsafeQueryError as e:
            return {"message": str(e)}


    return response




