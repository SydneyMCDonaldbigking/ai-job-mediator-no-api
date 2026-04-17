"""TinyDB database layer for JSON storage."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tinydb import Query, TinyDB
from tinydb.table import Table

from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """TinyDB wrapper for resume matcher data."""

    _master_resume_lock = asyncio.Lock()

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: TinyDB | None = None

    @property
    def db(self) -> TinyDB:
        """Lazy initialization of TinyDB instance."""
        if self._db is None:
            self._db = TinyDB(self.db_path)
        return self._db

    @property
    def resumes(self) -> Table:
        """Resumes table."""
        return self.db.table("resumes")

    @property
    def jobs(self) -> Table:
        """Job descriptions table."""
        return self.db.table("jobs")

    @property
    def improvements(self) -> Table:
        """Improvement results table."""
        return self.db.table("improvements")

    @property
    def multilingual_resume_assets(self) -> Table:
        """Singleton table storing active resume ids by language."""
        return self.db.table("multilingual_resume_assets")

    @property
    def scheduled_scan_settings(self) -> Table:
        """Singleton table storing scheduled scan config and state."""
        return self.db.table("scheduled_scan_settings")

    @property
    def discovered_jobs(self) -> Table:
        """Persisted jobs found by automated scans."""
        return self.db.table("discovered_jobs")

    def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            self._db.close()
            self._db = None

    # Resume operations
    def create_resume(
        self,
        content: str,
        content_type: str = "md",
        filename: str | None = None,
        is_master: bool = False,
        parent_id: str | None = None,
        processed_data: dict[str, Any] | None = None,
        processing_status: str = "pending",
        cover_letter: str | None = None,
        outreach_message: str | None = None,
        title: str | None = None,
        original_markdown: str | None = None,
    ) -> dict[str, Any]:
        """Create a new resume entry.

        processing_status: "pending", "processing", "ready", "failed"
        """
        resume_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc: dict[str, Any] = {
            "resume_id": resume_id,
            "content": content,
            "content_type": content_type,
            "filename": filename,
            "is_master": is_master,
            "parent_id": parent_id,
            "processed_data": processed_data,
            "processing_status": processing_status,
            "cover_letter": cover_letter,
            "outreach_message": outreach_message,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        if original_markdown is not None:
            doc["original_markdown"] = original_markdown
        self.resumes.insert(doc)
        return doc

    async def create_resume_atomic_master(
        self,
        content: str,
        content_type: str = "md",
        filename: str | None = None,
        processed_data: dict[str, Any] | None = None,
        processing_status: str = "pending",
        cover_letter: str | None = None,
        outreach_message: str | None = None,
        original_markdown: str | None = None,
    ) -> dict[str, Any]:
        """Create a new resume with atomic master assignment.

        Uses an asyncio.Lock to prevent race conditions when multiple uploads
        happen concurrently and both try to become master. This avoids blocking
        the FastAPI event loop unlike threading.Lock.
        """
        async with self._master_resume_lock:
            current_master = self.get_master_resume()
            is_master = current_master is None

            # Recovery behavior: if the current master is stuck in failed or
            # processing state, promote the next upload to become the new master.
            if current_master and current_master.get("processing_status") in ("failed", "processing"):
                Resume = Query()
                self.resumes.update(
                    {"is_master": False},
                    Resume.resume_id == current_master["resume_id"],
                )
                is_master = True

            return self.create_resume(
                content=content,
                content_type=content_type,
                filename=filename,
                is_master=is_master,
                processed_data=processed_data,
                processing_status=processing_status,
                cover_letter=cover_letter,
                outreach_message=outreach_message,
                original_markdown=original_markdown,
            )

    def get_resume(self, resume_id: str) -> dict[str, Any] | None:
        """Get resume by ID."""
        Resume = Query()
        result = self.resumes.search(Resume.resume_id == resume_id)
        return result[0] if result else None

    def get_master_resume(self) -> dict[str, Any] | None:
        """Get the master resume if exists."""
        Resume = Query()
        result = self.resumes.search(Resume.is_master == True)
        return result[0] if result else None

    def update_resume(self, resume_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update resume by ID.

        Raises:
            ValueError: If resume not found.
        """
        Resume = Query()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated_count = self.resumes.update(updates, Resume.resume_id == resume_id)

        if not updated_count:
            raise ValueError(f"Resume not found: {resume_id}")

        result = self.get_resume(resume_id)
        if not result:
            raise ValueError(f"Resume disappeared after update: {resume_id}")

        return result

    def delete_resume(self, resume_id: str) -> bool:
        """Delete resume by ID."""
        Resume = Query()
        removed = self.resumes.remove(Resume.resume_id == resume_id)
        return len(removed) > 0

    def list_resumes(self) -> list[dict[str, Any]]:
        """List all resumes."""
        return list(self.resumes.all())

    def get_multilingual_resume_assets(self) -> dict[str, Any]:
        """Get the singleton multilingual resume registry."""
        rows = list(self.multilingual_resume_assets.all())
        return rows[0] if rows else {}

    def save_multilingual_resume_assets(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upsert the singleton multilingual resume registry."""
        self.multilingual_resume_assets.truncate()
        self.multilingual_resume_assets.insert(payload)
        return payload

    def update_multilingual_resume_asset(self, language: str, resume_id: str) -> dict[str, Any]:
        """Update the active resume slot for one language."""
        current = self.get_multilingual_resume_assets()
        field_map = {
            "en": "resume_en_id",
            "ja": "resume_ja_id",
            "zh": "resume_zh_id",
        }
        field_name = field_map.get(language)
        if not field_name:
            raise ValueError(f"Unsupported resume language: {language}")

        normalized = {
            "candidate_id": current.get("candidate_id", "default"),
            "resume_en_id": current.get("resume_en_id"),
            "resume_ja_id": current.get("resume_ja_id"),
            "resume_zh_id": current.get("resume_zh_id"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        normalized[field_name] = resume_id
        return self.save_multilingual_resume_assets(normalized)

    def get_scheduled_scan_config(self) -> dict[str, Any]:
        """Get the singleton scheduled scan config."""
        rows = list(self.scheduled_scan_settings.all())
        return rows[0] if rows else {}

    def save_scheduled_scan_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upsert the singleton scheduled scan config."""
        current = self.get_scheduled_scan_config()
        merged = {**current, **payload}
        self.scheduled_scan_settings.truncate()
        self.scheduled_scan_settings.insert(merged)
        return merged

    def list_recent_discovered_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recently discovered jobs ordered by discovered time desc."""
        jobs = list(self.discovered_jobs.all())
        jobs.sort(key=lambda item: item.get("discovered_at", ""), reverse=True)
        return jobs[:limit]

    def get_discovered_jobs_map(self) -> dict[str, dict[str, Any]]:
        """Return discovered jobs keyed by stable job key."""
        return {
            str(item.get("job_key")): item
            for item in self.discovered_jobs.all()
            if item.get("job_key")
        }

    def upsert_discovered_jobs(self, jobs: list[dict[str, Any]]) -> None:
        """Insert or replace discovered jobs by key."""
        Job = Query()
        for job in jobs:
            key = job.get("job_key")
            if not key:
                continue
            existing = self.discovered_jobs.search(Job.job_key == key)
            if existing:
                self.discovered_jobs.update(job, Job.job_key == key)
            else:
                self.discovered_jobs.insert(job)

    def set_master_resume(self, resume_id: str) -> bool:
        """Set a resume as the master, unsetting any existing master.

        Returns False if the resume doesn't exist.
        """
        Resume = Query()

        # First verify the target resume exists
        target = self.resumes.search(Resume.resume_id == resume_id)
        if not target:
            logger.warning("Cannot set master: resume %s not found", resume_id)
            return False

        # Unset current master
        self.resumes.update({"is_master": False}, Resume.is_master == True)
        # Set new master
        updated = self.resumes.update(
            {"is_master": True}, Resume.resume_id == resume_id
        )
        return len(updated) > 0

    # Job operations
    def create_job(self, content: str, resume_id: str | None = None) -> dict[str, Any]:
        """Create a new job description entry."""
        job_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "job_id": job_id,
            "content": content,
            "resume_id": resume_id,
            "created_at": now,
        }
        self.jobs.insert(doc)
        return doc

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get job by ID."""
        Job = Query()
        result = self.jobs.search(Job.job_id == job_id)
        return result[0] if result else None

    def update_job(self, job_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        """Update a job by ID."""
        Job = Query()
        updated = self.jobs.update(updates, Job.job_id == job_id)
        if not updated:
            return None
        return self.get_job(job_id)

    # Improvement operations
    def create_improvement(
        self,
        original_resume_id: str,
        tailored_resume_id: str,
        job_id: str,
        improvements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create an improvement result entry."""
        request_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "request_id": request_id,
            "original_resume_id": original_resume_id,
            "tailored_resume_id": tailored_resume_id,
            "job_id": job_id,
            "improvements": improvements,
            "created_at": now,
        }
        self.improvements.insert(doc)
        return doc

    def get_improvement_by_tailored_resume(
        self, tailored_resume_id: str
    ) -> dict[str, Any] | None:
        """Get improvement record by tailored resume ID.

        This is used to retrieve the job context for on-demand
        cover letter and outreach message generation.
        """
        Improvement = Query()
        result = self.improvements.search(
            Improvement.tailored_resume_id == tailored_resume_id
        )
        return result[0] if result else None

    # Stats
    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        return {
            "total_resumes": len(self.resumes),
            "total_jobs": len(self.jobs),
            "total_improvements": len(self.improvements),
            "total_discovered_jobs": len(self.discovered_jobs),
            "has_master_resume": self.get_master_resume() is not None,
        }

    def reset_database(self) -> None:
        """Reset the database by truncating all tables and clearing uploads."""
        # Truncate tables
        self.resumes.truncate()
        self.jobs.truncate()
        self.improvements.truncate()
        self.multilingual_resume_assets.truncate()
        self.scheduled_scan_settings.truncate()
        self.discovered_jobs.truncate()

        # Clear uploads directory
        uploads_dir = settings.data_dir / "uploads"
        if uploads_dir.exists():
            import shutil

            shutil.rmtree(uploads_dir)
            uploads_dir.mkdir(parents=True, exist_ok=True)


# Global database instance
db = Database()
