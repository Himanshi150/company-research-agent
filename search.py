"""Web research using the Tavily Search API."""

import os
from typing import Any, Dict, List
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


CATEGORIES = {
    "overview": "{company} company overview what does {company} do official annual report",
    "size_locations": "{company} number of employees headquarters office locations annual report LinkedIn",
    "news": "{company} latest news recent announcement 2026",
    "leadership": "{company} CEO executive leadership management team official",
    "contacts": "{company} public professional contact investor relations media contact official",
}


def normalize_url(url: str) -> str:
    """Remove tracking fragments and return a stable, clickable URL."""
    if not url:
        return ""
    return url.strip().split("#", 1)[0]


def validate_url(url: str) -> bool:
    """Accept only ordinary public HTTP(S) source URLs."""
    try:
        parsed = urlparse(normalize_url(url))
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def deduplicate_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate Tavily results by normalized URL and filter malformed items."""
    unique: Dict[str, Dict[str, Any]] = {}
    for item in results:
        url = normalize_url(str(item.get("url", "")))
        if not validate_url(url):
            continue
        title = str(item.get("title") or "Untitled source").strip()
        content = str(item.get("content") or item.get("snippet") or "").strip()
        published = item.get("published_date") or item.get("date") or ""
        score = item.get("score")
        record = {
            "title": title,
            "url": url,
            "content": content,
            "published_date": str(published).strip() if published else "",
            "score": score,
        }
        previous = unique.get(url)
        if previous is None or (record["score"] or 0) > (previous["score"] or 0):
            unique[url] = record
    return list(unique.values())


def get_tavily_client(api_key: str | None = None) -> TavilyClient:
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("TAVILY_API_KEY")
        except Exception:
            key = None
    if not key:
        raise ValueError("TAVILY_API_KEY is missing. Add it to .env or Streamlit secrets.")
    return TavilyClient(api_key=key)


def research_company(company_name: str, api_key: str | None = None) -> List[Dict[str, Any]]:
    """Run targeted searches and return deduplicated evidence for Gemini."""
    company_name = company_name.strip()
    if len(company_name) < 2:
        raise ValueError("Please enter a valid company name.")

    client = get_tavily_client(api_key)
    all_results: List[Dict[str, Any]] = []

    for category, template in CATEGORIES.items():
        query = template.format(company=company_name)
        try:
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=False,
                include_raw_content=False,
            )
            for item in response.get("results", []) or []:
                item = dict(item)
                item["category"] = category
                all_results.append(item)
        except Exception as exc:
            message = str(exc).lower()
            if "rate" in message or "429" in message:
                raise RuntimeError("Tavily rate limit reached. Please wait and try again.") from exc
            raise RuntimeError(f"Tavily search failed: {exc}") from exc

    results = deduplicate_results(all_results)
    results.sort(key=lambda x: (x.get("score") or 0), reverse=True)
    if not results:
        raise RuntimeError("No public search results were found. Check the company name or try a more specific name.")
    return results
