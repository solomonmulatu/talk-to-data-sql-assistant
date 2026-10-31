from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from introspection.prompts import SUMMARY_SYSTEM_PROMPT
from src.talk_to_data.config import settings

from pydantic import BaseModel
from typing import Optional, Literal


class ChartConfig(BaseModel):
    should_visualize: bool
    chart_type: Optional[
        Literal["bar", "line", "scatter", "pie"]
    ] = None
    x: Optional[str] = None
    y: Optional[str] = None
    title: Optional[str] = None


class AnalysisResult(BaseModel):
    summary: str
    chart: ChartConfig



class Summarizer:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.openai_chat_model,
            temperature=0,
        ).with_structured_output(
            AnalysisResult
        )

    def analyze(self, question: str, df):
        if df.empty:
            return AnalysisResult(
                summary="The query returned no results.",
                chart=ChartConfig(
                    should_visualize=False
                )
            )

        preview = df.head(20).to_markdown(index=False)

        prompt = f"""
           User question: {question}

           Query results:
           {preview}

           Analyze the results.

           1. Provide a concise, factual summary.
           2. Decide whether visualization is useful.
           3. If useful, select an appropriate chart.
           4. Only use column names that exist in the results.
           5. Never invent statistics.
           """

        return self.llm.invoke(prompt)



