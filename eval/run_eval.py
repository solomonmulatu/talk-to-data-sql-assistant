"""Run a lightweight contract evaluation against the Talk to Data API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import requests


DEFAULT_URL = "http://localhost:8000/query"
DEFAULT_QUESTIONS = Path(__file__).with_name("questions.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL, help=f"POST endpoint (default: {DEFAULT_URL})")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="Evaluation questions JSON file")
    parser.add_argument("--timeout", type=float, default=60, help="Request timeout in seconds")
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N questions; 0 runs all")
    parser.add_argument("--report", type=Path, help="Optional path to write the detailed JSON report")
    return parser.parse_args()


def load_cases(path: Path, limit: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as file:
        cases = json.load(file)
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError("The questions file must contain a JSON array of question objects.")
    if limit > 0:
        cases = cases[:limit]
    return cases


def decode_chart(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def chart_types(chart: dict[str, Any] | None) -> list[str]:
    traces = chart.get("data", []) if chart else []
    if not isinstance(traces, list):
        return []
    return [str(trace.get("type", "scatter")).lower() for trace in traces if isinstance(trace, dict)]


def fallback_chart_type(rows: Any) -> str | None:
    """Mirror the Streamlit app's basic chart-from-rows fallback."""
    if not isinstance(rows, list) or not rows:
        return None
    try:
        frame = pd.DataFrame.from_records(rows) if all(isinstance(row, dict) for row in rows) else pd.DataFrame(rows)
    except (TypeError, ValueError):
        return None
    if frame.empty or len(frame.columns) == 0:
        return None

    numeric_columns = frame.select_dtypes(include="number").columns.tolist()
    category_columns = [column for column in frame.columns if column not in numeric_columns]
    if numeric_columns and category_columns:
        return "bar" if not frame[[category_columns[0], numeric_columns[0]]].dropna().empty else None
    if numeric_columns:
        return "histogram" if not frame[numeric_columns[0]].dropna().empty else None
    return "bar" if not frame[category_columns[0]].dropna().empty else None


def evaluate_case(case: dict[str, Any], url: str, timeout: float) -> dict[str, Any]:
    case_id = case.get("id", "unnamed")
    question = case.get("question", "")
    expected_chart = case.get("expected_visualization", "none")
    errors: list[str] = []
    result: dict[str, Any] = {
        "id": case_id,
        "question": question,
        "expected": "error" if expected_chart == "none" else "success",
        "passed": False,
        "checks": {},
    }

    if not isinstance(question, str) or not question.strip():
        result["errors"] = ["Question is missing or empty."]
        return result

    try:
        response = requests.post(
            url,
            params={"query": question},
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        result["errors"] = [f"Request failed: {exc}"]
        return result

    result["http_status"] = response.status_code
    try:
        body = response.json()
    except requests.exceptions.JSONDecodeError:
        result["errors"] = [f"Response was not JSON: {response.text[:400]}"]
        return result

    if not isinstance(body, dict):
        result["errors"] = ["Response JSON was not an object."]
        return result

    is_error = body.get("result") == "ERROR" or response.status_code >= 400
    if expected_chart == "none":
        result["checks"]["rejected_as_unanswerable"] = is_error
        if not is_error:
            errors.append("Expected the API to reject an unanswerable question.")
    else:
        result["checks"]["http_success"] = response.ok
        if not response.ok:
            errors.append(f"API returned HTTP {response.status_code}.")
        result["checks"]["summary_present"] = isinstance(body.get("summary"), str) and bool(body["summary"].strip())
        if not result["checks"]["summary_present"]:
            errors.append("Response is missing a non-empty summary.")

        data = body.get("data")
        result["checks"]["data_is_list"] = isinstance(data, list)
        if not isinstance(data, list):
            errors.append("Response `data` must be a list.")
        else:
            result["checks"]["data_has_rows"] = bool(data)
            if not data:
                errors.append("Response `data` list is empty.")

        chart = decode_chart(body.get("chart"))
        found_types = chart_types(chart)
        fallback_type = fallback_chart_type(data)
        result["chart_types"] = found_types
        result["fallback_chart_type"] = fallback_type
        if expected_chart == "bar":
            chart_ok = any(trace_type in {"bar", "histogram"} for trace_type in found_types) or fallback_type in {"bar", "histogram"}
        elif expected_chart == "line":
            chart_ok = any(trace_type in {"scatter", "scattergl"} for trace_type in found_types)
        else:
            chart_ok = True
        result["checks"]["expected_chart_present"] = chart_ok
        if not chart_ok:
            observed = found_types or ([fallback_type] if fallback_type else [])
            errors.append(f"Expected a {expected_chart} chart, found {observed or 'no chart or chartable rows'}.")

    result["passed"] = not errors
    result["errors"] = errors
    if is_error and isinstance(body.get("message"), str):
        result["api_message"] = body["message"]
    if isinstance(body.get("data"), list):
        result["returned_fields"] = list(body["data"][0].keys()) if body["data"] and isinstance(body["data"][0], dict) else []
    return result


def main() -> int:
    args = parse_args()
    try:
        cases = load_cases(args.questions, args.limit)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Could not load questions: {exc}", file=sys.stderr)
        return 2

    if not cases:
        print("No evaluation questions found.", file=sys.stderr)
        return 2

    print(f"Evaluating {len(cases)} question(s) at {args.url}\n")
    results = []
    for index, case in enumerate(cases, start=1):
        item = evaluate_case(case, args.url, args.timeout)
        results.append(item)
        status = "PASS" if item["passed"] else "FAIL"
        print(f"[{status}] {index:02d} {item['id']}: {item['question']}")
        for error in item.get("errors", []):
            print(f"       - {error}")
        if item.get("api_message"):
            print(f"       API: {item['api_message']}")

    passed = sum(bool(item["passed"]) for item in results)
    report = {
        "url": args.url,
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    print(f"\nSummary: {passed}/{len(results)} passed; {len(results) - passed} failed.")

    if args.report:
        try:
            args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"Detailed report written to {args.report}")
        except OSError as exc:
            print(f"Could not write report: {exc}", file=sys.stderr)
            return 2

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
