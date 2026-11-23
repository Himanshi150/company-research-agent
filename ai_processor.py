"""Gemini-powered report generation with evidence and URL validation."""

import json
import os
import re
import time
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

UNAVAILABLE = "Not publicly available"
MODEL_NAME = "gemini-flash-lite-latest"
MODEL_FALLBACKS = (
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3-flash-preview",
)

REPORT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "company_name": {"type": "STRING"},
        "overview": {"type": "STRING"},
        "industry": {"type": "STRING"},
        "employee_size": {"type": "STRING"},
        "headquarters": {"type": "STRING"},
        "locations": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "recent_news": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "headline": {"type": "STRING"},
                    "date": {"type": "STRING"},
                    "summary": {"type": "STRING"},
                    "source_urls": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": [
                    "headline", "date", "summary", "source_urls"
                ]
            }
        },
        "decision_makers": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "designation": {"type": "STRING"},
                    "contact": {"type": "STRING"},
                    "source_urls": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": [
                    "name", "designation", "contact", "source_urls"
                ]
            }
        },
        "talking_points": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "point": {"type": "STRING"},
                    "source_urls": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    }
                },
                "required": ["point", "source_urls"]
            }
        },
        "sources": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        }
    },
    "required": [
        "company_name", "overview", "industry", "employee_size",
        "headquarters", "locations", "recent_news",
        "decision_makers", "talking_points", "sources"
    ]
}


def get_gemini_client(
    api_key: Optional[str] = None
) -> genai.Client:

    key = api_key or os.getenv("GEMINI_API_KEY")

    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            key = None

    if not key:
        raise ValueError(
            "GEMINI_API_KEY is missing. Add it to .env or Streamlit secrets."
        )

    return genai.Client(api_key=key)


def format_evidence(
    results: Iterable[Dict[str, Any]]
) -> str:

    lines = []

    for index, result in enumerate(results, start=1):
        lines.append(
            f"SOURCE {index}\n"
            f"URL: {result.get('url', '')}\n"
            f"TITLE: {result.get('title', 'Untitled')}\n"
            f"DATE: {result.get('published_date') or UNAVAILABLE}\n"
            f"CONTENT: {result.get('content') or 'No snippet available'}"
        )

    return "\n\n".join(lines)


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON even if Gemini surrounds it with Markdown."""

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

        if not match:
            raise ValueError("Gemini did not return valid JSON.")

        return json.loads(match.group(0))


def validate_report(
    report: Dict[str, Any],
    company_name: str,
    search_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Normalize report and allow only URLs from search evidence."""

    allowed = {
        str(item["url"]).strip()
        for item in search_results
        if item.get("url")
    }

    def clean_urls(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []

        return [
            url.strip()
            for url in value
            if isinstance(url, str) and url.strip() in allowed
        ]

    report["company_name"] = str(
        report.get("company_name") or company_name
    ).strip()

    for key in (
        "overview", "industry", "employee_size", "headquarters"
    ):
        value = report.get(key)
        report[key] = (
            str(value).strip()
            if isinstance(value, str) and value.strip()
            else UNAVAILABLE
        )

    locations = report.get("locations", [])
    report["locations"] = (
        [
            str(value).strip()
            for value in locations
            if isinstance(value, str) and value.strip()
        ]
        if isinstance(locations, list)
        else []
    )

    news_items = report.get("recent_news", [])
    if not isinstance(news_items, list):
        news_items = []

    for news in news_items:
        if not isinstance(news, dict):
            continue

        for key in ("headline", "date", "summary"):
            news[key] = str(news.get(key) or UNAVAILABLE).strip()

        news["source_urls"] = clean_urls(news.get("source_urls"))

    report["recent_news"] = [
        item for item in news_items if isinstance(item, dict)
    ]

    people = report.get("decision_makers", [])
    if not isinstance(people, list):
        people = []

    for person in people:
        if not isinstance(person, dict):
            continue

        for key in ("name", "designation", "contact"):
            person[key] = str(person.get(key) or UNAVAILABLE).strip()

        person["source_urls"] = clean_urls(person.get("source_urls"))

    report["decision_makers"] = [
        person for person in people if isinstance(person, dict)
    ]

    points = report.get("talking_points", [])
    if not isinstance(points, list):
        points = []

    for point in points:
        if not isinstance(point, dict):
            continue

        point["point"] = str(
            point.get("point") or UNAVAILABLE
        ).strip()

        point["source_urls"] = clean_urls(point.get("source_urls"))

    report["talking_points"] = [
        point for point in points if isinstance(point, dict)
    ]

    report["sources"] = clean_urls(report.get("sources"))

    if not report["sources"]:
        report["sources"] = sorted(allowed)

    return report


def generate_report(
    company_name: str,
    search_results: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = MODEL_NAME
) -> Dict[str, Any]:

    if not search_results:
        raise ValueError(
            "No search evidence was available for report generation."
        )

    evidence = format_evidence(search_results[:20])

    prompt = f"""
You are a concise business research analyst.
Create a one-page report for {company_name}.

Use ONLY the evidence below. Never invent facts or URLs.
If unavailable, write exactly: "{UNAVAILABLE}".
Include supporting source URLs. Never guess contact details.
Include at most 5 news items and exactly 3 meeting talking points.
Return only valid JSON matching the required schema.

EVIDENCE:
{evidence}
"""

    client = get_gemini_client(api_key)
    response = None
    last_error = None

    for model_name in MODEL_FALLBACKS:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=REPORT_SCHEMA
                )
            )
            if getattr(response, "text", None):
                break
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if any(code in message for code in ("404", "503", "429", "UNAVAILABLE", "NOT_FOUND", "RESOURCE_EXHAUSTED")):
                continue
            raise RuntimeError(f"Gemini API failed: {message}") from exc

    if response is None or not getattr(response, "text", None):
        raise RuntimeError(
            "Gemini is temporarily unavailable. Please wait a minute and try again."
        ) from last_error

    try:
        report = extract_json(response.text)

    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid JSON returned by Gemini: {exc}"
        ) from exc

    if not isinstance(report, dict):
        raise RuntimeError(
            "Gemini response was not a JSON object."
        )

    return validate_report(
        report,
        company_name,
        search_results
    )
