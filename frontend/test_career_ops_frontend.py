import importlib.util
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


FRONTEND_DIR = Path(__file__).resolve().parent
APP_PATH = FRONTEND_DIR / "app.py"


def load_frontend_app_module():
    if str(FRONTEND_DIR) not in sys.path:
        sys.path.insert(0, str(FRONTEND_DIR))
    spec = importlib.util.spec_from_file_location("frontend_app_module", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MockHTTPResponse:
    def __init__(self, payload=None, status_code=200, content=b"", headers=None):
        self._payload = payload
        self.status_code = status_code
        self.text = ""
        self.reason_phrase = ""
        self.content = content
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class RecordingAsyncClient:
    requests = []
    responses = {}

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses[("GET", url)]

    async def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses[("POST", url)]

    async def put(self, url, **kwargs):
        self.requests.append(("PUT", url, kwargs))
        return self.responses[("PUT", url)]


class CareerOpsFrontendFormattingTests(unittest.TestCase):
    def test_test_mode_uses_local_runtime_dependencies(self):
        temp_root = FRONTEND_DIR / ".tmp-tests" / "frontend-app-test-mode"
        shutil.rmtree(temp_root, ignore_errors=True)
        data_dir = temp_root / "data"
        public_dir = temp_root / "public"

        with patch.dict(
            os.environ,
            {
                "CHAINLIT_TEST_MODE": "1",
                "CHAINLIT_APP_DATA_DIR": str(data_dir),
                "CHAINLIT_APP_PUBLIC_DIR": str(public_dir),
            },
            clear=False,
        ):
            frontend_app = load_frontend_app_module()

        self.assertTrue(frontend_app.TEST_MODE_ENABLED)
        self.assertEqual(frontend_app.DATA_DIR, data_dir)
        self.assertEqual(frontend_app.PUBLIC_DIR, public_dir)
        self.assertEqual(type(frontend_app.backend).__name__, "InMemoryTestBackend")
        self.assertEqual(type(frontend_app.get_data_layer()).__name__, "LocalJsonDataLayer")
        self.assertTrue((public_dir / "auto-login.js").exists())

        shutil.rmtree(temp_root, ignore_errors=True)

    def test_build_tool_actions_include_resume_and_pdf_controls(self):
        frontend_app = load_frontend_app_module()

        labels = [action.label for action in frontend_app.build_tool_actions()]

        self.assertIn("重新上传主简历", labels)
        self.assertIn("删除当前对话", labels)
        self.assertIn("下载 ATS PDF", labels)

    def test_build_tool_actions_include_doda_search(self):
        frontend_app = load_frontend_app_module()

        labels = [action.label for action in frontend_app.build_tool_actions()]

        self.assertIn("doda 搜索岗位", labels)

    def test_render_portals_config_outputs_yaml(self):
        frontend_app = load_frontend_app_module()

        rendered = frontend_app.render_portals_config(
            {
                "title_filter": {"positive": ["engineer"]},
                "tracked_companies": [
                    {
                        "name": "Anthropic",
                        "careers_url": "https://jobs.example.com",
                    }
                ],
            }
        )

        self.assertIn("tracked_companies:", rendered)
        self.assertIn("Anthropic", rendered)

    def test_download_elements_include_mime_types(self):
        frontend_app = load_frontend_app_module()
        response = frontend_app.ImproveResumeResponse.model_validate(
            {
                "request_id": "req-1",
                "data": {
                    "resume_id": "tailored-1",
                    "job_id": "job-1",
                    "improvements": [],
                    "markdownImproved": "# Tailored Resume",
                    "cover_letter": "Cover letter body",
                    "outreach_message": "Outreach body",
                    "diff_summary": None,
                    "refinement_stats": None,
                    "warnings": [],
                },
            }
        )

        with patch.object(
            frontend_app.cl,
            "File",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            elements = frontend_app.build_download_elements(response)
            pdf_element = frontend_app.build_pdf_download_element(
                {"filename": "tailored_resume.pdf", "content": b"%PDF-1.4"}
            )

        self.assertEqual([element.mime for element in elements], ["text/markdown"] * 3)
        self.assertEqual(pdf_element.mime, "application/pdf")

    def test_parse_portals_config_input_accepts_yaml(self):
        frontend_app = load_frontend_app_module()

        parsed = frontend_app.parse_portals_config_input(
            "tracked_companies:\n"
            "  - name: Anthropic\n"
            "    careers_url: https://jobs.example.com\n"
        )

        self.assertEqual(parsed["tracked_companies"][0]["name"], "Anthropic")

    def test_parse_portals_config_input_rejects_list_payload(self):
        frontend_app = load_frontend_app_module()

        with self.assertRaises(ValueError):
            frontend_app.parse_portals_config_input("- just\n- a\n- list\n")

    def test_format_career_ops_evaluation_includes_market_signals(self):
        frontend_app = load_frontend_app_module()

        message = frontend_app.format_career_ops_evaluation(
            frontend_app.CareerOpsEvaluateResponse.model_validate(
                {
                    "request_id": "req-1",
                    "data": {
                        "overall_score": 4.2,
                        "overall_label": "Strong fit",
                        "executive_summary": "Resume aligns well.",
                        "archetype": "Builder",
                        "af_scores": {
                            "A": 4.5,
                            "B": 4.0,
                            "C": 4.1,
                            "D": 3.6,
                            "E": 4.3,
                            "F": 4.4,
                        },
                        "dimensions": [],
                        "tailoring_priorities": ["Highlight distributed systems."],
                        "interview_focus": ["Discuss scaling wins."],
                        "keyword_targets": ["Python", "FastAPI"],
                        "market_data": {
                            "role_query": "Senior Backend Engineer",
                            "company_name": "OpenAI",
                            "salary_mentions": ["$155,000"],
                            "demand_summary": "Demand is active.",
                            "compensation_summary": "Comp looks above market.",
                            "sources": [
                                {
                                    "title": "Levels.fyi listing",
                                    "url": "https://example.com/levels",
                                    "snippet": "Senior backend salary data.",
                                }
                            ],
                        },
                    },
                }
            )
        )

        self.assertIn("A-F 职位评估", message)
        self.assertIn("$155,000", message)
        self.assertIn("Levels.fyi listing", message)

    def test_format_scan_result_includes_new_offer(self):
        frontend_app = load_frontend_app_module()

        message = frontend_app.format_scan_result(
            frontend_app.CareerOpsScanResponse.model_validate(
                {
                    "request_id": "scan-1",
                    "data": {
                        "scanned_companies": 2,
                        "total_jobs_found": 4,
                        "filtered_out": 1,
                        "duplicates": 1,
                        "new_offers": [
                            {
                                "title": "Senior Backend Engineer",
                                "url": "https://example.com/jobs/1",
                                "company": "Anthropic",
                                "location": "Remote",
                                "source": "greenhouse",
                            }
                        ],
                        "errors": [],
                    },
                }
            )
        )

        self.assertIn("Senior Backend Engineer", message)
        self.assertIn("Anthropic", message)

    def test_format_seek_search_result_includes_keywords_and_company(self):
        frontend_app = load_frontend_app_module()

        message = frontend_app.format_seek_search_result(
            frontend_app.SeekSearchResponse.model_validate(
                {
                    "plan": {
                        "resume_id": "resume-1",
                        "source": "seek",
                        "candidate_profile_summary": "Python backend engineer",
                        "keywords": ["python backend engineer", "platform engineer"],
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
                            "salary": "$180k-$200k",
                            "work_type": "Full time",
                            "listed_at": "2d ago",
                            "job_url": "https://www.seek.com.au/job/123",
                            "summary": "Build APIs",
                            "match_score": 0.91,
                        }
                    ],
                    "stats": {
                        "keywords_generated": 2,
                        "queries_attempted": 2,
                        "queries_succeeded": 2,
                        "raw_jobs_found": 7,
                        "jobs_after_dedupe": 4,
                    },
                    "errors": [],
                }
            )
        )

        self.assertIn("SEEK", message)
        self.assertIn("python backend engineer", message)
        self.assertIn("Example Co", message)
        self.assertIn("关键词数", message)
        self.assertIn("职位卡片", message)
        self.assertIn("### SEEK 岗位", message)
        self.assertIn("来源分布", message)
        self.assertIn("SEEK `1`", message)
        self.assertIn("来源：`SEEK`", message)
        self.assertIn("匹配等级：`高`", message)
        self.assertIn("[打开岗位](https://www.seek.com.au/job/123)", message)

    def test_format_seek_search_result_preserves_doda_source_label(self):
        frontend_app = load_frontend_app_module()

        message = frontend_app.format_seek_search_result(
            frontend_app.SeekSearchResponse.model_validate(
                {
                    "plan": {
                        "resume_id": "resume-ja-1",
                        "source": "doda",
                        "candidate_profile_summary": "Python と FastAPI を使ったバックエンド経験。",
                        "keywords": ["バックエンドエンジニア"],
                        "location": "東京",
                    },
                    "jobs": [
                        {
                            "job_id": "doda:https://doda.jp/job/123",
                            "source": "doda",
                            "language": "ja",
                            "search_keyword": "バックエンドエンジニア",
                            "title": "バックエンドエンジニア",
                            "company": "OpenAI Japan",
                            "location": "東京",
                            "salary": "年収700万円",
                            "work_type": None,
                            "listed_at": None,
                            "job_url": "https://doda.jp/job/123",
                            "summary": "Python / FastAPI",
                            "match_score": 0.91,
                            "raw_location_text": "東京",
                            "raw_salary_text": "年収700万円",
                        }
                    ],
                    "stats": {
                        "keywords_generated": 1,
                        "queries_attempted": 1,
                        "queries_succeeded": 1,
                        "raw_jobs_found": 2,
                        "jobs_after_dedupe": 1,
                    },
                    "errors": [],
                }
            )
        )

        self.assertIn("doda", message)
        self.assertIn("OpenAI Japan", message)
        self.assertIn("职位卡片", message)
        self.assertIn("### doda 岗位", message)
        self.assertIn("doda `1`", message)
        self.assertIn("来源：`doda`", message)
        self.assertIn("匹配等级：`高`", message)
        self.assertIn("[打开岗位](https://doda.jp/job/123)", message)

    def test_format_scheduled_scan_settings_includes_assets_and_recent_jobs(self):
        frontend_app = load_frontend_app_module()

        message = frontend_app.format_scheduled_scan_settings(
            frontend_app.ScheduledScanSettingsResponse.model_validate(
                {
                    "config": {
                        "enabled": True,
                        "run_time_local": "09:00",
                        "timezone": "Australia/Sydney",
                        "seek_enabled": True,
                        "doda_enabled": False,
                        "boss_enabled": False,
                        "feishu_enabled": True,
                        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
                        "high_score_threshold": 0.8,
                        "last_run_at": "2026-04-17T00:05:00+00:00",
                        "last_run_date_local": "2026-04-17",
                        "last_run_status": "success",
                        "last_error": None,
                        "last_result_counts": {
                            "seek": {"raw_jobs_found": 7, "new_jobs": 2}
                        },
                    },
                    "assets": {
                        "candidate_id": "default",
                        "resume_en_id": "resume-en",
                        "resume_ja_id": None,
                        "resume_zh_id": None,
                        "updated_at": "2026-04-17T00:00:00+00:00",
                    },
                    "recent_new_jobs": [
                        {
                            "job_key": "seek:https://www.seek.com.au/job/123",
                            "source": "seek",
                            "resume_language": "en",
                            "title": "Senior Backend Engineer",
                            "company": "Example Co",
                            "location": "Sydney NSW",
                            "job_url": "https://www.seek.com.au/job/123",
                            "summary": "Build APIs",
                            "match_score": 0.91,
                            "discovered_at": "2026-04-17T00:05:00+00:00",
                            "first_seen_at": "2026-04-17T00:05:00+00:00",
                            "last_seen_at": "2026-04-17T00:05:00+00:00",
                            "is_new": True,
                            "status": "new",
                        }
                    ],
                    "high_score_unapplied_jobs": [
                        {
                            "job_key": "seek:https://www.seek.com.au/job/123",
                            "source": "seek",
                            "resume_language": "en",
                            "title": "Senior Backend Engineer",
                            "company": "Example Co",
                            "location": "Sydney NSW",
                            "job_url": "https://www.seek.com.au/job/123",
                            "summary": "Build APIs",
                            "match_score": 0.91,
                            "discovered_at": "2026-04-17T00:05:00+00:00",
                            "first_seen_at": "2026-04-17T00:05:00+00:00",
                            "last_seen_at": "2026-04-17T00:05:00+00:00",
                            "is_new": True,
                            "status": "new",
                        },
                        {
                            "job_key": "seek:https://www.seek.com.au/job/456",
                            "source": "seek",
                            "resume_language": "en",
                            "title": "Staff Platform Engineer",
                            "company": "Example Co",
                            "location": "Melbourne VIC",
                            "job_url": "https://www.seek.com.au/job/456",
                            "summary": "Build platforms",
                            "match_score": 0.96,
                            "discovered_at": "2026-04-17T00:05:00+00:00",
                            "first_seen_at": "2026-04-17T00:05:00+00:00",
                            "last_seen_at": "2026-04-17T00:05:00+00:00",
                            "is_new": True,
                            "status": "new",
                        }
                    ],
                }
            )
        )

        self.assertIn("自动扫描设置", message)
        self.assertIn("09:00", message)
        self.assertIn("SEEK", message)
        self.assertIn("飞书", message)
        self.assertIn("高分未投递岗位", message)
        self.assertIn("Senior Backend Engineer", message)
        self.assertIn("Staff Platform Engineer", message)
        self.assertIn("SCAN_RESULTS_PAYLOAD::", message)

    def test_build_discovered_job_actions_creates_apply_buttons(self):
        frontend_app = load_frontend_app_module()

        actions = frontend_app.build_discovered_job_actions(
            [
                frontend_app.DiscoveredJobRecord.model_validate(
                    {
                        "job_key": "seek:https://www.seek.com.au/job/123",
                        "source": "seek",
                        "resume_language": "en",
                        "title": "Senior Backend Engineer",
                        "company": "Example Co",
                        "location": "Sydney NSW",
                        "job_url": "https://www.seek.com.au/job/123",
                        "summary": "Build APIs",
                        "match_score": 0.91,
                        "discovered_at": "2026-04-17T00:05:00+00:00",
                        "first_seen_at": "2026-04-17T00:05:00+00:00",
                        "last_seen_at": "2026-04-17T00:05:00+00:00",
                        "is_new": True,
                        "status": "new",
                    }
                )
            ]
        )

        self.assertEqual(actions[0].payload["job_key"], "seek:https://www.seek.com.au/job/123")
        self.assertEqual(actions[0].payload["status"], "applied")

    def test_serialize_discovered_job_for_panel_includes_apply_action_label(self):
        frontend_app = load_frontend_app_module()

        job = frontend_app.DiscoveredJobRecord.model_validate(
            {
                "job_key": "seek:https://www.seek.com.au/job/123",
                "source": "seek",
                "resume_language": "en",
                "title": "Senior Backend Engineer",
                "company": "Example Co",
                "location": "Sydney NSW",
                "job_url": "https://www.seek.com.au/job/123",
                "summary": "Build APIs",
                "match_score": 0.91,
                "discovered_at": "2026-04-17T00:05:00+00:00",
                "first_seen_at": "2026-04-17T00:05:00+00:00",
                "last_seen_at": "2026-04-17T00:05:00+00:00",
                "is_new": True,
                "status": "new",
            }
        )

        payload = frontend_app.serialize_discovered_job_for_panel(job)

        self.assertTrue(payload["can_mark_applied"])
        self.assertEqual(
            payload["apply_action_label"],
            "标记已投递: Example Co / Senior Backend Engineer",
        )

    def test_build_scheduled_scan_form_actions_includes_form_controls(self):
        frontend_app = load_frontend_app_module()

        actions = frontend_app.build_scheduled_scan_form_actions(
            frontend_app.ScheduledScanConfig(
                enabled=True,
                run_time_local="09:00",
                timezone="Australia/Sydney",
                seek_enabled=True,
                doda_enabled=False,
                boss_enabled=False,
                feishu_enabled=True,
                feishu_webhook_url="https://open.feishu.cn/fake-webhook",
                high_score_threshold=0.8,
            )
        )

        labels = [action.label for action in actions]
        self.assertIn("设置时间", labels)
        self.assertIn("设置阈值", labels)
        self.assertIn("设置飞书 Webhook", labels)

    def test_build_scheduled_scan_chat_settings_contains_visual_inputs(self):
        frontend_app = load_frontend_app_module()

        chat_settings = frontend_app.build_scheduled_scan_chat_settings(
            frontend_app.ScheduledScanConfig(
                enabled=True,
                run_time_local="09:00",
                timezone="Australia/Sydney",
                seek_enabled=True,
                doda_enabled=False,
                boss_enabled=False,
                feishu_enabled=True,
                feishu_webhook_url="https://open.feishu.cn/fake-webhook",
                high_score_threshold=0.8,
            ),
            frontend_app.MultilingualResumeAssets(
                candidate_id="candidate-1",
                resume_en_id="resume-en",
                resume_ja_id=None,
                resume_zh_id=None,
            ),
        )

        inputs = chat_settings.inputs
        self.assertEqual(inputs[0].id, "scheduled_scan_enabled")
        self.assertEqual(inputs[1].id, "scheduled_scan_run_time_local")
        self.assertEqual(inputs[2].id, "scheduled_scan_timezone")
        self.assertEqual(inputs[3].id, "scheduled_scan_high_score_threshold")
        self.assertEqual(inputs[4].id, "scheduled_scan_seek_enabled")
        self.assertFalse(inputs[4].disabled)
        self.assertTrue(inputs[5].disabled)
        self.assertTrue(inputs[6].disabled)
        self.assertEqual(inputs[7].id, "scheduled_scan_feishu_enabled")
        self.assertEqual(inputs[8].id, "scheduled_scan_feishu_webhook_url")

    def test_build_resume_assets_panel_payload_marks_existing_and_missing_resumes(self):
        frontend_app = load_frontend_app_module()

        payload = frontend_app.build_resume_assets_panel_payload(
            frontend_app.MultilingualResumeAssets(
                candidate_id="default",
                resume_en_id="resume-en",
                resume_ja_id=None,
                resume_zh_id="resume-zh",
            ),
            [
                frontend_app.ResumeSummary(
                    resume_id="resume-en",
                    filename="resume-en.pdf",
                    is_master=True,
                    processing_status="ready",
                    updated_at="2026-05-04T08:00:00+00:00",
                ),
                frontend_app.ResumeSummary(
                    resume_id="resume-zh",
                    filename="resume-zh.pdf",
                    is_master=False,
                    processing_status="ready",
                    updated_at="2026-05-03T07:00:00+00:00",
                ),
            ],
        )

        self.assertTrue(payload["resumes"]["en"]["exists"])
        self.assertEqual(payload["resumes"]["en"]["filename"], "resume-en.pdf")
        self.assertEqual(payload["resumes"]["en"]["updated_at"], "2026-05-04T08:00:00+00:00")
        self.assertFalse(payload["resumes"]["ja"]["exists"])
        self.assertTrue(payload["resumes"]["zh"]["exists"])
        self.assertTrue(payload["search"]["seek"]["enabled"])
        self.assertEqual(payload["search"]["seek"]["missing"], None)
        self.assertFalse(payload["search"]["doda"]["enabled"])
        self.assertEqual(payload["search"]["doda"]["missing"], "ja")

    def test_parse_scheduled_scan_field_input_accepts_time_and_threshold(self):
        frontend_app = load_frontend_app_module()

        time_value = frontend_app.parse_scheduled_scan_field_input("run_time_local", "21:30")
        threshold_value = frontend_app.parse_scheduled_scan_field_input(
            "high_score_threshold",
            "0.85",
        )

        self.assertEqual(time_value, "21:30")
        self.assertEqual(threshold_value, 0.85)

    def test_normalize_scheduled_scan_settings_input_parses_visual_form_values(self):
        frontend_app = load_frontend_app_module()

        normalized = frontend_app.normalize_scheduled_scan_settings_input(
            {
                "scheduled_scan_enabled": True,
                "scheduled_scan_run_time_local": "21:30",
                "scheduled_scan_timezone": "Australia/Sydney",
                "scheduled_scan_high_score_threshold": 0.9,
                "scheduled_scan_seek_enabled": True,
                "scheduled_scan_doda_enabled": False,
                "scheduled_scan_boss_enabled": False,
                "scheduled_scan_feishu_enabled": True,
                "scheduled_scan_feishu_webhook_url": "none",
            }
        )

        self.assertEqual(normalized["run_time_local"], "21:30")
        self.assertEqual(normalized["high_score_threshold"], 0.9)
        self.assertIsNone(normalized["feishu_webhook_url"])


class CareerOpsFrontendBackendClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.frontend_app = load_frontend_app_module()
        RecordingAsyncClient.requests = []
        RecordingAsyncClient.responses = {}

    async def test_evaluate_job_posts_resume_and_jd(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/evaluate-job",
            ): MockHTTPResponse(
                {
                    "request_id": "req-1",
                    "data": {
                        "overall_score": 4.0,
                        "overall_label": "Good fit",
                        "executive_summary": "Looks solid.",
                        "archetype": "Operator",
                        "af_scores": {"A": 4.0, "B": 4.0, "C": 4.0, "D": 4.0, "E": 4.0, "F": 4.0},
                        "dimensions": [],
                        "tailoring_priorities": [],
                        "interview_focus": [],
                        "keyword_targets": [],
                        "market_data": None,
                    },
                }
            )
        }

        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            result = await self.frontend_app.ResumeMatcherBackend(
                "http://backend"
            ).evaluate_job("resume text", "job description")

        self.assertEqual(result.data.overall_label, "Good fit")
        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/evaluate-job"))
        self.assertEqual(kwargs["json"]["resume"], "resume text")
        self.assertEqual(kwargs["json"]["job_description"], "job description")

    async def test_scan_jobs_calls_scan_endpoint(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/scan-jobs",
            ): MockHTTPResponse(
                {
                    "request_id": "scan-1",
                    "data": {
                        "scanned_companies": 1,
                        "total_jobs_found": 2,
                        "filtered_out": 0,
                        "duplicates": 0,
                        "new_offers": [],
                        "errors": [],
                    },
                }
            )
        }

        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            result = await self.frontend_app.ResumeMatcherBackend(
                "http://backend"
            ).scan_jobs()

        self.assertEqual(result.data.scanned_companies, 1)
        self.assertEqual(
            RecordingAsyncClient.requests[0][:2],
            ("POST", "http://backend/api/scan-jobs"),
        )

    async def test_generate_tailored_pdf_posts_resume_and_jd(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/generate-tailored-pdf",
            ): MockHTTPResponse(
                content=b"%PDF-1.4 fake pdf bytes",
                headers={
                    "Content-Disposition": 'attachment; filename="tailored_resume.pdf"'
                },
            )
        }

        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            result = await self.frontend_app.ResumeMatcherBackend(
                "http://backend"
            ).generate_tailored_pdf("resume text", "job description")

        self.assertEqual(result["filename"], "tailored_resume.pdf")
        self.assertEqual(result["content"], b"%PDF-1.4 fake pdf bytes")
        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/generate-tailored-pdf"))
        self.assertEqual(kwargs["json"]["resume"], "resume text")
        self.assertEqual(kwargs["json"]["job_description"], "job description")

    async def test_get_and_update_portals_config_use_config_routes(self):
        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/config/portals",
            ): MockHTTPResponse(
                {
                    "title_filter": {"positive": ["engineer"]},
                    "search_queries": [],
                    "tracked_companies": [],
                }
            ),
            (
                "PUT",
                "http://backend/api/v1/config/portals",
            ): MockHTTPResponse(
                {
                    "title_filter": {"positive": ["engineer"]},
                    "search_queries": [],
                    "tracked_companies": [
                        {
                            "name": "Anthropic",
                            "careers_url": "https://jobs.example.com",
                            "enabled": True,
                        }
                    ],
                }
            ),
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            current = await backend.get_portals_config()
            updated = await backend.update_portals_config(
                {
                    "tracked_companies": [
                        {
                            "name": "Anthropic",
                            "careers_url": "https://jobs.example.com",
                            "enabled": True,
                        }
                    ]
                }
            )

        self.assertEqual(current.title_filter.positive, ["engineer"])
        self.assertEqual(updated.tracked_companies[0].name, "Anthropic")
        self.assertEqual(
            RecordingAsyncClient.requests[0][:2],
            ("GET", "http://backend/api/v1/config/portals"),
        )
        self.assertEqual(
            RecordingAsyncClient.requests[1][:2],
            ("PUT", "http://backend/api/v1/config/portals"),
        )

    async def test_search_seek_jobs_posts_resume_id(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/v1/jobs/search/seek",
            ): MockHTTPResponse(
                {
                    "plan": {
                        "resume_id": "resume-1",
                        "source": "seek",
                        "candidate_profile_summary": "Python backend engineer",
                        "keywords": ["python backend engineer"],
                        "location": "Sydney NSW",
                    },
                    "jobs": [],
                    "stats": {
                        "keywords_generated": 1,
                        "queries_attempted": 1,
                        "queries_succeeded": 1,
                        "raw_jobs_found": 0,
                        "jobs_after_dedupe": 0,
                    },
                    "errors": [],
                }
            )
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            await backend.search_seek_jobs("resume-1")

        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/v1/jobs/search/seek"))
        self.assertEqual(kwargs["json"]["resume_id"], "resume-1")

    async def test_search_doda_jobs_posts_resume_id(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/v1/jobs/search/doda",
            ): MockHTTPResponse(
                {
                    "plan": {
                        "resume_id": "resume-ja-1",
                        "source": "doda",
                        "candidate_profile_summary": "Python と FastAPI を使ったバックエンド経験。",
                        "keywords": ["バックエンドエンジニア"],
                        "location": "東京",
                    },
                    "jobs": [],
                    "stats": {
                        "keywords_generated": 1,
                        "queries_attempted": 1,
                        "queries_succeeded": 1,
                        "raw_jobs_found": 0,
                        "jobs_after_dedupe": 0,
                    },
                    "errors": [],
                }
            )
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            await backend.search_doda_jobs("resume-ja-1")

        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/v1/jobs/search/doda"))
        self.assertEqual(kwargs["json"]["resume_id"], "resume-ja-1")

    async def test_upload_resume_posts_language_form_field(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/v1/resumes/upload",
            ): MockHTTPResponse(
                {
                    "message": "stored",
                    "request_id": "req-upload",
                    "resume_id": "resume-ja",
                    "processing_status": "ready",
                    "is_master": False,
                }
            )
        }
        temp_file = FRONTEND_DIR / ".tmp-tests" / "resume-ja.pdf"
        temp_file.parent.mkdir(parents=True, exist_ok=True)
        temp_file.write_bytes(b"%PDF-1.4\n")

        try:
            backend = self.frontend_app.ResumeMatcherBackend("http://backend")
            with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
                result = await backend.upload_resume(
                    str(temp_file),
                    "resume-ja.pdf",
                    "application/pdf",
                    resume_language="ja",
                )
        finally:
            temp_file.unlink(missing_ok=True)

        self.assertEqual(result.resume_id, "resume-ja")
        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/v1/resumes/upload"))
        self.assertEqual(kwargs["data"]["resume_language"], "ja")

    async def test_list_resumes_includes_master_query_param(self):
        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/resumes/list",
            ): MockHTTPResponse(
                {
                    "request_id": "resume-list",
                    "data": [
                        {
                            "resume_id": "resume-en",
                            "filename": "resume-en.pdf",
                            "is_master": True,
                            "parent_id": None,
                            "processing_status": "ready",
                            "created_at": "2026-05-04T08:00:00+00:00",
                            "updated_at": "2026-05-04T08:00:00+00:00",
                            "title": None,
                        }
                    ],
                }
            )
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            result = await backend.list_resumes(include_master=True)

        self.assertEqual(result.data[0].resume_id, "resume-en")
        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("GET", "http://backend/api/v1/resumes/list"))
        self.assertEqual(kwargs["params"]["include_master"], "true")

    async def test_get_and_update_scheduled_scan_settings_use_scheduled_scan_routes(self):
        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/scheduled-scan/settings",
            ): MockHTTPResponse(
                {
                    "config": {
                        "enabled": True,
                        "run_time_local": "09:00",
                        "timezone": "Australia/Sydney",
                        "seek_enabled": True,
                        "doda_enabled": False,
                        "boss_enabled": False,
                        "feishu_enabled": True,
                        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
                        "high_score_threshold": 0.8,
                        "last_run_at": None,
                        "last_run_date_local": None,
                        "last_run_status": None,
                        "last_error": None,
                        "last_result_counts": {},
                    },
                    "assets": {
                        "candidate_id": "default",
                        "resume_en_id": "resume-en",
                        "resume_ja_id": None,
                        "resume_zh_id": None,
                        "updated_at": None,
                    },
                    "recent_new_jobs": [],
                    "high_score_unapplied_jobs": [],
                }
            ),
            (
                "PUT",
                "http://backend/api/v1/scheduled-scan/settings",
            ): MockHTTPResponse(
                {
                    "config": {
                        "enabled": True,
                        "run_time_local": "21:30",
                        "timezone": "Australia/Sydney",
                        "seek_enabled": True,
                        "doda_enabled": False,
                        "boss_enabled": False,
                        "feishu_enabled": True,
                        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
                        "high_score_threshold": 0.85,
                        "last_run_at": None,
                        "last_run_date_local": None,
                        "last_run_status": None,
                        "last_error": None,
                        "last_result_counts": {},
                    },
                    "assets": {
                        "candidate_id": "default",
                        "resume_en_id": "resume-en",
                        "resume_ja_id": None,
                        "resume_zh_id": None,
                        "updated_at": None,
                    },
                    "recent_new_jobs": [],
                    "high_score_unapplied_jobs": [],
                }
            ),
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            current = await backend.get_scheduled_scan_settings()
            updated = await backend.update_scheduled_scan_settings(
                {
                    "enabled": True,
                    "run_time_local": "21:30",
                    "timezone": "Australia/Sydney",
                    "seek_enabled": True,
                    "doda_enabled": False,
                    "boss_enabled": False,
                    "feishu_enabled": True,
                    "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
                    "high_score_threshold": 0.85,
                }
            )

        self.assertTrue(current.config.enabled)
        self.assertEqual(updated.config.run_time_local, "21:30")
        self.assertTrue(updated.config.feishu_enabled)
        self.assertEqual(updated.config.high_score_threshold, 0.85)
        self.assertEqual(
            RecordingAsyncClient.requests[0][:2],
            ("GET", "http://backend/api/v1/scheduled-scan/settings"),
        )
        self.assertEqual(
            RecordingAsyncClient.requests[1][:2],
            ("PUT", "http://backend/api/v1/scheduled-scan/settings"),
        )

    async def test_mark_discovered_job_status_posts_job_key_and_status(self):
        RecordingAsyncClient.responses = {
            (
                "POST",
                "http://backend/api/v1/scheduled-scan/jobs/status",
            ): MockHTTPResponse(
                {
                    "job_key": "seek:https://www.seek.com.au/job/123",
                    "source": "seek",
                    "resume_language": "en",
                    "title": "Senior Backend Engineer",
                    "company": "Example Co",
                    "location": "Sydney NSW",
                    "job_url": "https://www.seek.com.au/job/123",
                    "summary": "Build APIs",
                    "match_score": 0.91,
                    "discovered_at": "2026-04-17T00:05:00+00:00",
                    "first_seen_at": "2026-04-17T00:05:00+00:00",
                    "last_seen_at": "2026-04-17T00:05:00+00:00",
                    "is_new": True,
                    "status": "applied",
                }
            )
        }

        backend = self.frontend_app.ResumeMatcherBackend("http://backend")
        with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
            result = await backend.mark_discovered_job_status(
                "seek:https://www.seek.com.au/job/123",
                "applied",
            )

        self.assertEqual(result.status, "applied")
        method, url, kwargs = RecordingAsyncClient.requests[0]
        self.assertEqual((method, url), ("POST", "http://backend/api/v1/scheduled-scan/jobs/status"))
        self.assertEqual(kwargs["json"]["job_key"], "seek:https://www.seek.com.au/job/123")
        self.assertEqual(kwargs["json"]["status"], "applied")


if __name__ == "__main__":
    unittest.main()
