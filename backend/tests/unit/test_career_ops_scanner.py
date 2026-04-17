"""Unit tests for Career Ops portal scanning helpers."""

from pathlib import Path

from app.career_ops.scanner import (
    build_title_filter,
    detect_api,
    ensure_portals_config,
    parse_greenhouse_jobs,
)


def test_detect_api_handles_greenhouse_ashby_and_lever():
    assert detect_api({"api": "https://boards-api.greenhouse.io/v1/boards/acme/jobs"}) == {
        "type": "greenhouse",
        "url": "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
    }
    assert detect_api({"careers_url": "https://jobs.ashbyhq.com/acme"}) == {
        "type": "ashby",
        "url": "https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=true",
    }
    assert detect_api({"careers_url": "https://jobs.lever.co/acme"}) == {
        "type": "lever",
        "url": "https://api.lever.co/v0/postings/acme",
    }


def test_build_title_filter_applies_positive_and_negative_keywords():
    matcher = build_title_filter(
        {
            "positive": ["AI Engineer", "Solutions Architect"],
            "negative": ["Junior", "Intern"],
        }
    )

    assert matcher("Senior AI Engineer") is True
    assert matcher("Junior AI Engineer") is False
    assert matcher("Backend Platform Engineer") is False


def test_parse_greenhouse_jobs_normalizes_payload():
    jobs = parse_greenhouse_jobs(
        {
            "jobs": [
                {
                    "title": "Senior AI Engineer",
                    "absolute_url": "https://jobs.example.com/1",
                    "location": {"name": "Remote"},
                }
            ]
        },
        company_name="Acme",
    )

    assert jobs == [
        {
            "title": "Senior AI Engineer",
            "url": "https://jobs.example.com/1",
            "company": "Acme",
            "location": "Remote",
            "source": "greenhouse",
        }
    ]


def test_ensure_portals_config_bootstraps_example(tmp_path: Path):
    config_path = tmp_path / "portals.yml"
    example_path = tmp_path / "portals.example.yml"
    example_path.write_text("title_filter:\n  positive:\n    - AI\n", encoding="utf-8")

    result_path = ensure_portals_config(config_path=config_path, example_path=example_path)

    assert result_path == config_path
    assert config_path.exists()
    assert "positive" in config_path.read_text(encoding="utf-8")
