"""Gemini-powered report generation with evidence and URL validation."""
# Connects to Gemini and generates a structured research report.

import json
import os
import re
from typing import Any, Dict, Iterable, List

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

UNAVAILABLE = "Not publicly available"

REPORT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "company_name": {"type": "STRING"},
        "overview": {"type": "STRING"},
        "industry": {"type": "STRING"},
        "employee_size": {"type": "STRING"},
        "headquarters": {"type": "STRING"},
        "locations": {"type": "ARRAY", "items": {"type": "STRING"}},
        "recent_news": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "headline": {"type": "STRING"}, "date": {"type": "STRING"}, "summary": {"type": "STRING"}, "source_urls": {"type": "ARRAY", "items": {"type": "STRING"}}
        }, "required": ["headline", "date", "summary", "source_urls"]}},
        "decision_makers": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "name": {"type": "STRING"}, "designation": {"type": "STRING"}, "contact": {"type": "STRING"}, "source_urls": {"type": "ARRAY", "items": {"type": "STRING"}}
        }, "required": ["name", "designation", "contact", "source_urls"]}},
        "talking_points": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "point": {"type": "STRING"}, "source_urls": {"type": "ARRAY", "items": {"type": "STRING"}}
        }, "required": ["point", "source_urls"]}},
        "sources": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["company_name", "overview", "industry", "employee_size", "headquarters", "locations", "recent_news", "decision_makers", "talking_points", "sources"],
}


def get_gemini_client(api_key: str | None = None) -> genai.Client:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            key = None
    if not key:
        raise ValueError("GEMINI_API_KEY is missing. Add it to .env or Streamlit secrets.")
    return genai.Client(api_key=key)


def format_evidence(results: Iterable[Dict[str, Any]]) -> str:
    lines = []
    for index, result in enumerate(results, start=1):
        lines.append(
            f"SOURCE {index}\nURL: {result['url']}\nTITLE: {result['title']}\n"
            f"DATE: {result.get('published_date') or 'Not publicly available'}\n"
            f"CONTENT: {result.get('content') or 'No snippet available'}"
        )
    return "\n\n".join(lines)


def extract_json(text: str) -> Dict[str, Any]:
    """Extract JSON even if the model surrounds it with prose or markdown."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"```\s*$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise ValueError("Gemini did not return valid JSON.")
        return json.loads(match.group(0))


def validate_report(report: Dict[str, Any], company_name: str, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize types and remove citations absent from the original search evidence."""
    allowed = {str(item["url"]).strip() for item in search_results if item.get("url")}

    def clean_urls(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [url for url in value if isinstance(url, str) and url.strip() in allowed]

    report.setdefault("company_name", company_name)
    report["company_name"] = str(report.get("company_name") or company_name).strip()
    for key in ("overview", "industry", "employee_size", "headquarters"):
        value = report.get(key)
        report[key] = str(value).strip() if isinstance(value, str) and value.strip() else UNAVAILABLE

    for key in ("locations",):
        value = report.get(key)
        report[key] = [str(v).strip() for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []

    for news in report.get("recent_news", []) if isinstance(report.get("recent_news", []), list) else []:
        if not isinstance(news, dict):
            continue
        for key in ("headline", "date", "summary"):
            news[key] = str(news.get(key) or UNAVAILABLE).strip()
        news["source_urls"] = clean_urls(news.get("source_urls"))

    for person in report.get("decision_makers", []) if isinstance(report.get("decision_makers", []), list) else []:
        if not isinstance(person, dict):
            continue
        for key in ("name", "designation", "contact"):
            person[key] = str(person.get(key) or UNAVAILABLE).strip()
        person["source_urls"] = clean_urls(person.get("source_urls"))

    for point in report.get("talking_points", []) if isinstance(report.get("talking_points", []), list) else []:
        if not isinstance(point, dict):
            continue
        point["point"] = str(point.get("point") or UNAVAILABLE).strip()
        point["source_urls"] = clean_urls(point.get("source_urls"))

    report["sources"] = clean_urls(report.get("sources"))
    if not report["sources"]:
        report["sources"] = sorted(allowed)
    return report


def generate_report(company_name: str, search_results: List[Dict[str, Any]], api_key: str | None = None, model: str = "gemini-2.5-flash") -> Dict[str, Any]:
    if not search_results:
        raise ValueError("No search evidence was available for report generation.")

    evidence = format_evidence(search_results)
    prompt = f"""You are a careful business research analyst. Create a one-page company research report.

Company requested: {company_name}

Rules:
1. Use ONLY the SOURCE evidence below. Never use prior knowledge or invent URLs, news, counts, locations, people, contact details, or qualifications.
2. If evidence is missing or ambiguous, write exactly: "{UNAVAILABLE}".
3. For every factual claim, include supporting source_urls. Do not cite a URL not shown in evidence.
4. Do not guess or construct email addresses or phone numbers. Professional contact information may include a verified public general or department address; otherwise use "{UNAVAILABLE}".
5. Recent news means recent in the evidence; include at most 5 entries.
6. Talking points must be exactly 3 practical first-meeting points grounded in the evidence.
7. Locations must be strings; do not infer office locations.
8. Return only valid JSON matching the required schema.

EVIDENCE:
{evidence}
"""

    try:
        client = get_gemini_client(api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=REPORT_SCHEMA,
            ),
        )
    except Exception as exc:
        message = str(exc)
        if "429" in message or "rate" in message.lower():
            raise RuntimeError("Gemini rate limit reached. Please wait and try again.") from exc
        raise RuntimeError(f"Gemini API failed: {message}") from exc

    if not getattr(response, "text", None):
        raise RuntimeError("Gemini returned an empty response.")
    try:
        report = extract_json(response.text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Invalid JSON returned by Gemini: {exc}") from exc
    if not isinstance(report, dict):
        raise RuntimeError("Gemini response was not a JSON object.")
    return validate_report(report, company_name, search_results)
