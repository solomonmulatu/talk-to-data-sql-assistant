"""Friendly Streamlit frontend for a Talk to Data FastAPI service."""

import json
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.io as pio
import requests
import streamlit as st


API_URL = "http://localhost:8000/query"
HTTP_METHOD = "POST"
QUESTION_PARAMETER = "query"
REQUEST_TIMEOUT_SECONDS = 60
EXAMPLE_QUESTIONS = [
    "How many customers are in each country?",
    "Which artists have the most albums?",
    "What are the 10 longest tracks?",
    "How much revenue did each country generate?",
]

st.set_page_config(page_title="Talk to Data", page_icon="📊", layout="centered")
st.title("Talk to your data")
st.write("Ask a question in plain language and explore the answer, chart, and result rows.")
st.caption("Use one of the examples below, or type your own question.")


def parse_response(response: requests.Response) -> dict[str, Any]:
    """Decode the API response and ensure it has the expected shape."""
    try:
        body = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        excerpt = response.text[:500] or "(empty response)"
        raise ValueError(f"The API returned invalid JSON: {excerpt}") from exc

    if not isinstance(body, dict):
        raise ValueError("The API response must be a JSON object.")
    if body.get("result") == "ERROR":
        return body
    if "summary" not in body:
        raise ValueError("The API response is missing the `summary` field.")
    if "data" not in body:
        raise ValueError("The API response is missing the `data` field.")
    if body["data"] is not None and not isinstance(body["data"], list):
        raise ValueError("The API response `data` field must be a list of records.")
    return body


def build_chart_from_rows(rows: list[Any]) -> Any | None:
    """Create a sensible fallback chart when the API returns rows but no figure."""
    if not rows:
        return None

    frame = pd.DataFrame.from_records(rows) if all(isinstance(row, dict) for row in rows) else pd.DataFrame(rows)
    if frame.empty or len(frame.columns) == 0:
        return None

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    category_columns = [column for column in frame.columns if column not in numeric_columns]

    if numeric_columns and category_columns:
        category = category_columns[0]
        measure = numeric_columns[0]
        chart_data = frame[[category, measure]].dropna()
        if chart_data.empty:
            return None
        if chart_data[category].nunique() > 20:
            chart_data = chart_data.nlargest(20, measure)
        chart_data = chart_data.sort_values(measure, ascending=True)
        figure = px.bar(
            chart_data,
            x=measure,
            y=category,
            orientation="h",
            title=f"{measure.replace('_', ' ').title()} by {category.replace('_', ' ').title()}",
            labels={category: category.replace("_", " ").title(), measure: measure.replace("_", " ").title()},
        )
    elif numeric_columns:
        measure = numeric_columns[0]
        figure = px.histogram(
            frame,
            x=measure,
            title=f"Distribution of {measure.replace('_', ' ').title()}",
            labels={measure: measure.replace("_", " ").title()},
        )
    else:
        category = category_columns[0]
        chart_data = frame[category].dropna().value_counts().head(20).rename_axis(category).reset_index(name="count")
        if chart_data.empty:
            return None
        figure = px.bar(
            chart_data.sort_values("count", ascending=True),
            x="count",
            y=category,
            orientation="h",
            title=f"Rows by {category.replace('_', ' ').title()}",
            labels={category: category.replace("_", " ").title(), "count": "Count"},
        )

    figure.update_layout(height=max(340, min(620, 34 * len(frame))), margin=dict(l=12, r=12, t=55, b=16))
    return figure


def render_chart(chart_value: Any, rows: list[Any]) -> None:
    """Render the API chart, or derive one from returned records when it is absent."""
    figure = None
    if chart_value is not None and chart_value != "":
        try:
            if isinstance(chart_value, str):
                figure = pio.from_json(chart_value)
            elif isinstance(chart_value, dict):
                figure = pio.from_json(json.dumps(chart_value))
            else:
                raise ValueError("Chart must be a Plotly JSON string, JSON object, or null.")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            st.warning(f"The API chart could not be read ({exc}); I’ll try to chart the returned rows instead.")

    if figure is None:
        figure = build_chart_from_rows(rows)
        if figure is not None:
            st.caption("Chart generated from the returned rows.")

    if figure is None:
        st.info("No chart is available. The API needs to return chart data or rows that can be charted.")
        return

    st.plotly_chart(figure, use_container_width=True, config={"responsive": True})

st.subheader("Try a question")
if "question_text" not in st.session_state:
    st.session_state["question_text"] = ""

selected_example = st.selectbox(
    "Example questions",
    ["Choose an example…", *EXAMPLE_QUESTIONS],
)
if st.button("Use example", use_container_width=True, disabled=selected_example == "Choose an example…"):
    st.session_state["question_text"] = selected_example
    st.rerun()

with st.form("query_form", clear_on_submit=False):
    question = st.text_area(
        "Your question",
        placeholder="For example: Which artists have the most albums?",
        height=105,
        key="question_text",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("✨  Find my answer", type="primary", use_container_width=True)

if submitted:
    if not question.strip():
        st.warning("Type a question first and I’ll take a look.")
    else:
        try:
            with st.spinner("Looking through your data…"):
                request_values = {QUESTION_PARAMETER: question.strip()}
                if HTTP_METHOD == "GET":
                    response = requests.get(
                        API_URL,
                        params=request_values,
                        headers={"Accept": "application/json"},
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                else:
                    response = requests.post(
                        API_URL,
                        params=request_values,
                        headers={"Accept": "application/json"},
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
            if not response.ok:
                detail = response.text[:1000] or response.reason
                st.error(f"The API returned HTTP {response.status_code}: {detail}")
            else:
                st.session_state["talk_to_data_result"] = parse_response(response)
                st.session_state["talk_to_data_question"] = question.strip()
        except requests.exceptions.Timeout:
            st.error(f"That took longer than {REQUEST_TIMEOUT_SECONDS} seconds. Please try again.")
        except requests.exceptions.ConnectionError:
            st.error("I couldn’t reach the data service. Check that your FastAPI app is running.")
        except requests.exceptions.RequestException as exc:
            st.error(f"The request didn’t go through: {exc}")
        except ValueError as exc:
            st.error(str(exc))

result = st.session_state.get("talk_to_data_result")
if result is not None:
    st.markdown("---")
    if result.get("result") == "ERROR":
        st.error(result.get("message") or "I couldn’t answer that question from this database.")
        st.caption("Try asking about a table or topic available in your database.")
    else:
        st.subheader("Your answer")
        summary = result.get("summary")
        if summary is None or summary == "":
            st.info("The service didn’t return a written summary this time.")
        else:
            with st.container(border=True):
                st.write(summary)

        rows = result.get("data") or []
        st.subheader("Result rows")
        if rows:
            frame = pd.DataFrame.from_records(rows) if all(isinstance(row, dict) for row in rows) else pd.DataFrame(rows)
            st.dataframe(frame, use_container_width=True, hide_index=True)
            st.caption(f"{len(rows):,} row(s) returned")
        else:
            st.info("No rows came back for this question.")

        st.subheader("Chart")
        render_chart(result.get("chart"), rows)
