"""Unit tests for Career Ops market-data helpers."""

from app.career_ops.market_data import (
    build_market_search_queries,
    extract_salary_mentions,
    parse_duckduckgo_results,
)


def test_build_market_search_queries_includes_company_name():
    queries = build_market_search_queries("Senior Backend Engineer", company_name="OpenAI")

    assert len(queries) == 3
    assert "Senior Backend Engineer" in queries[0]
    assert "OpenAI" in queries[1]


def test_extract_salary_mentions_finds_ranges_and_single_values():
    mentions = extract_salary_mentions(
        "Comp ranges from $180,000 - $240,000 base. Another source says $210K total pay."
    )

    assert "$180,000 - $240,000" in mentions
    assert "$210K" in mentions


def test_parse_duckduckgo_results_extracts_titles_snippets_and_urls():
    html = """
    <html><body>
      <a class="result__a" href="https://example.com/salary">Senior Backend Engineer Salary</a>
      <a class="result__snippet">Average pay is $180,000 - $240,000 in San Francisco.</a>
    </body></html>
    """

    results = parse_duckduckgo_results(html)

    assert results[0]["title"] == "Senior Backend Engineer Salary"
    assert results[0]["url"] == "https://example.com/salary"
    assert "$180,000 - $240,000" in results[0]["snippet"]
