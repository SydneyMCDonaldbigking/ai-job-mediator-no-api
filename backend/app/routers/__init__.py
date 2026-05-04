"""API routers."""

from app.routers.chat_history import router as chat_history_router
from app.routers.career_ops import router as career_ops_router
from app.routers.config import router as config_router
from app.routers.enrichment import router as enrichment_router
from app.routers.health import router as health_router
from app.routers.jobs import router as jobs_router
from app.routers.resumes import router as resumes_router
from app.routers.scheduled_scan import router as scheduled_scan_router

__all__ = [
    "chat_history_router",
    "career_ops_router",
    "resumes_router",
    "jobs_router",
    "config_router",
    "health_router",
    "enrichment_router",
    "scheduled_scan_router",
]
