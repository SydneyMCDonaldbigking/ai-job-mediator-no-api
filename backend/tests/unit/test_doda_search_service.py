from pathlib import Path

from app.career_ops.doda_search import (
    build_doda_search_plan,
    localize_location_for_doda,
    normalize_doda_job,
    parse_doda_list_html,
)
from app.schemas.models import ResumeData


def test_build_doda_search_plan_generates_japanese_keywords():
    resume = ResumeData.model_validate(
        {
            "summary": "PythonとFastAPIを用いたバックエンド開発。AWS経験あり。",
            "workExperience": [
                {
                    "id": 1,
                    "title": "バックエンドエンジニア",
                    "company": "Acme",
                    "years": "2022-現在",
                    "description": ["API開発", "AWS基盤改善"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    plan = build_doda_search_plan(
        resume,
        resume_id="resume-ja-1",
        country="JP",
        location_text="Tokyo",
    )

    assert plan.source == "doda"
    assert plan.location == "東京"
    assert plan.keywords


def test_localize_location_for_doda_maps_common_city():
    assert localize_location_for_doda(country="JP", location_text="Tokyo") == "東京"


def test_parse_doda_list_html_extracts_required_fields():
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "doda"
        / "list_page_sample.html"
    ).read_text(encoding="utf-8")

    jobs = parse_doda_list_html(
        html,
        base_url="https://doda.jp",
        search_keyword="バックエンドエンジニア",
    )

    assert len(jobs) == 1
    assert jobs[0].title == "バックエンドエンジニア"
    assert jobs[0].company == "OpenAI Japan"
    assert jobs[0].location == "東京都"
    assert jobs[0].is_new is True


def test_normalize_doda_job_sets_source_and_job_id():
    normalized = normalize_doda_job(
        {
            "title": "バックエンドエンジニア",
            "company": "OpenAI Japan",
            "job_url": "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/",
            "location": "東京都",
            "salary": "年収700万円～1000万円",
            "summary": "Python / FastAPI",
            "search_keyword": "バックエンドエンジニア",
            "is_new": True,
        }
    )

    assert normalized.source == "doda"
    assert normalized.job_id.startswith("doda:")
    assert normalized.match_score == 0.0
