"""Unit tests for Career Ops market-data helpers."""

from app.career_ops.market_data import (
    build_market_search_queries,
    extract_salary_mentions,
    filter_market_results,
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


def test_filter_market_results_drops_unrelated_salary_pages():
    results = [
        {
            "title": "Senior Backend Engineer Salary in the United States",
            "url": "https://salary.com/backend",
            "snippet": "Median pay is $180,000 for senior backend engineers.",
        },
        {
            "title": "Microsoft Salaries | Levels.fyi",
            "url": "https://levels.fyi/microsoft",
            "snippet": "Compensation across Microsoft engineering roles.",
        },
        {
            "title": "TechCorp Salary Guide",
            "url": "https://example.com/techcorp-salary",
            "snippet": "TechCorp compensation data for backend hiring.",
        },
    ]

    filtered = filter_market_results(
        results,
        role_query="Senior Backend Engineer at TechCorp",
        company_name="TechCorp",
    )

    assert [item["title"] for item in filtered] == [
        "Senior Backend Engineer Salary in the United States",
        "TechCorp Salary Guide",
    ]


def test_filter_market_results_keeps_relevant_non_english_results():
    results = [
        {
            "title": "バックエンドエンジニア 年収ガイド",
            "url": "https://example.com/backend-salary-ja",
            "snippet": "OpenAI Japan のバックエンドエンジニア向け報酬データ。",
        },
        {
            "title": "Microsoft Salaries | Levels.fyi",
            "url": "https://levels.fyi/microsoft",
            "snippet": "Compensation across Microsoft engineering roles.",
        },
    ]

    filtered = filter_market_results(
        results,
        role_query="バックエンドエンジニア",
        company_name="OpenAI Japan",
    )

    assert [item["title"] for item in filtered] == [
        "バックエンドエンジニア 年収ガイド",
    ]
