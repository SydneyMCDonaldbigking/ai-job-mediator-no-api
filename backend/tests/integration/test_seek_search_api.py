from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app


@patch("app.routers.jobs.run_manual_seek_search")
async def test_post_manual_seek_search_returns_jobs(mock_run):
    mock_run.return_value = {
        "plan": {
            "resume_id": "resume-1",
            "source": "seek",
            "candidate_profile_summary": "Python backend engineer",
            "keywords": ["python backend engineer"],
            "location": "Sydney NSW",
        },
        "jobs": [
            {
                "job_id": "seek:https://www.seek.com.au/job/123",
                "source": "seek",
                "search_keyword": "python backend engineer",
                "title": "Senior Backend Engineer",
                "company": "Example Co",
                "location": "Sydney NSW",
                "salary": None,
                "work_type": None,
                "listed_at": "2d ago",
                "job_url": "https://www.seek.com.au/job/123",
                "summary": "Build APIs",
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
        response = await client.post("/api/v1/jobs/search/seek", json={"resume_id": "resume-1"})

    assert response.status_code == 200
    assert response.json()["jobs"][0]["company"] == "Example Co"
