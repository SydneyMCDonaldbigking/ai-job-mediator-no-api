from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app


@patch("app.routers.jobs.run_manual_doda_search")
async def test_post_manual_doda_search_returns_jobs(mock_run):
    mock_run.return_value = {
        "plan": {
            "resume_id": "resume-ja-1",
            "source": "doda",
            "candidate_profile_summary": "PythonとFastAPIを用いたバックエンド開発",
            "keywords": ["バックエンドエンジニア"],
            "location": "東京",
        },
        "jobs": [
            {
                "job_id": "doda:https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/",
                "source": "doda",
                "search_keyword": "バックエンドエンジニア",
                "title": "バックエンドエンジニア",
                "company": "OpenAI Japan",
                "location": "東京都",
                "salary": "年収700万円～1000万円",
                "work_type": None,
                "listed_at": None,
                "job_url": "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/",
                "summary": "Python / FastAPI",
                "match_score": 0.9,
            }
        ],
        "stats": {
            "keywords_generated": 1,
            "queries_attempted": 1,
            "queries_succeeded": 1,
            "raw_jobs_found": 1,
            "jobs_after_dedupe": 1,
        },
        "errors": [],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/jobs/search/doda", json={"resume_id": "resume-ja-1"})

    assert response.status_code == 200
    assert response.json()["plan"]["source"] == "doda"
    assert response.json()["jobs"][0]["company"] == "OpenAI Japan"
