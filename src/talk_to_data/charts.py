import plotly.express as px
import pandas as pd


class ChartGenerator:
    def __init__(self):
        pass



    def generate_chart(
        self,
        df: pd.DataFrame,
        chart_type: str,
        x: str,
        y: str,
        title: str = "Data Visualization"
    ):

        if df.empty:
            return None

        if x not in df.columns or y not in df.columns:
            raise ValueError("Invalid chart columns")

        if chart_type == "bar":
            fig = px.bar(df, x=x, y=y, title=title)

        elif chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title)

        elif chart_type == "scatter":
            fig = px.scatter(df, x=x, y=y, title=title)

        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title)

        else:
            raise ValueError("Unsupported chart type")

        fig.update_layout(
            template="plotly_white",
            autosize=True
        )

        return fig