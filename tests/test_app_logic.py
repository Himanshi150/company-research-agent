import pytest

from search import deduplicate_results, validate_url
from ai_processor import extract_json, validate_report


def test_validate_url_accepts_https():
    assert validate_url("https://example.com/company") is True


def test_validate_url_rejects_invalid():
    assert validate_url("javascript:alert(1)") is False


def test_deduplicate_results():
    results = [
        {"title": "A", "url": "https://example.com/a#section", "content": "one", "score": 0.5},
        {"title": "A2", "url": "https://example.com/a", "content": "two", "score": 0.9},
        {"title": "Bad", "url": "not-a-url", "content": "bad", "score": 1.0},
    ]
    output = deduplicate_results(results)
    assert len(output) == 1
    assert output[0]["score"] == 0.9


def test_extract_json_from_markdown():
    parsed = extract_json("```json\n{\"company_name\": \"Example\"}\n```")
    assert parsed["company_name"] == "Example"


def test_validate_report_flags_untrusted_urls():
    evidence = [{"url": "https://official.example.com", "title": "Official", "content": "Evidence"}]
    raw = {
        "company_name": "Example",
        "overview": "An overview",
        "industry": "Technology",
        "employee_size": "Not publicly available",
        "headquarters": "Not publicly available",
        "locations": [],
        "recent_news": [{"headline": "News", "date": "2026", "summary": "Summary", "source_urls": ["https://fake.example"]}],
        "decision_makers": [],
        "talking_points": [],
        "sources": ["https://fake.example"],
    }
    report = validate_report(raw, "Example", evidence)
    assert report["recent_news"][0]["source_urls"] == []
    assert report["sources"] == ["https://official.example.com"]


def test_missing_values_are_normalized():
    report = validate_report({}, "Example", [{"url": "https://official.example.com", "title": "Official"}])
    assert report["company_name"] == "Example"
    assert report["overview"] == "Not publicly available"
