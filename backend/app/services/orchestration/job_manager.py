from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.core.request_context import analysis_id_context
from app.schemas.ranking import AnalysisJobStatus, RankingResponse
from app.services.documents.upload_manager import SavedUpload, cleanup_upload_dir

logger = logging.getLogger(__name__)


@dataclass
class AnalysisJob:
    analysis_id: str
    status: str
    progress: int
    upload_dir: Path
    result: RankingResponse | None = None
    error: str | None = None
    cancel_requested: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AnalysisJobManager:
    def __init__(self) -> None:
        # Jobs are kept in process memory. This is enough for local/simple
        # deployments, but statuses disappear on restart and are not shared
        # across multiple backend workers.
        self._jobs: dict[str, AnalysisJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=settings.job_worker_count)

    def submit(
        self,
        pipeline_factory,
        job_upload: SavedUpload,
        cv_uploads: list[SavedUpload],
        top_k: int,
        upload_dir: Path,
    ) -> AnalysisJob:
        analysis_id = uuid4().hex
        job = AnalysisJob(analysis_id=analysis_id, status="pending", progress=0, upload_dir=upload_dir)
        with self._lock:
            self._jobs[analysis_id] = job
        # The heavy pipeline is run outside the request thread so the frontend
        # can poll progress instead of keeping one long HTTP request open.
        self._executor.submit(self._run, analysis_id, pipeline_factory, job_upload, cv_uploads, top_k)
        return job

    def get_status(self, analysis_id: str) -> AnalysisJobStatus | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if not job:
                return None
            return AnalysisJobStatus(
                analysis_id=job.analysis_id,
                status=job.status,
                progress=job.progress,
                result=job.result,
                error=job.error,
            )

    def cancel(self, analysis_id: str) -> AnalysisJobStatus | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if not job:
                return None
            if job.status in {"pending", "running"}:
                # Cancellation is cooperative: pending jobs can be stopped
                # immediately, while running jobs observe this flag only at
                # coarse checkpoints.
                job.cancel_requested = True
                if job.status == "pending":
                    job.status = "cancelled"
                    job.progress = 100
                    cleanup_upload_dir(job.upload_dir)
                job.updated_at = datetime.now(UTC)
            return AnalysisJobStatus(
                analysis_id=job.analysis_id,
                status=job.status,
                progress=job.progress,
                result=job.result,
                error=job.error,
            )

    def reset(self) -> None:
        with self._lock:
            for job in self._jobs.values():
                cleanup_upload_dir(job.upload_dir)
            self._jobs.clear()

    def _run(self, analysis_id: str, pipeline_factory, job_upload, cv_uploads, top_k: int) -> None:
        job = self._get_job(analysis_id)
        if not job:
            return
        if job.cancel_requested:
            self._set_status(analysis_id, "cancelled", 100)
            cleanup_upload_dir(job.upload_dir)
            return
        job = self._set_status(analysis_id, "running", 10)
        if not job:
            return
        token = analysis_id_context.set(analysis_id)
        try:
            result = pipeline_factory().run(job_upload, cv_uploads, top_k=top_k)
        except Exception:
            logger.exception("Analyse asynchrone echouee.", extra={"analysis_id": analysis_id})
            self._set_status(
                analysis_id,
                "failed",
                100,
                error="Analyse impossible. Consultez les logs serveur avec l'identifiant d'analyse.",
            )
        else:
            self._set_status(analysis_id, "completed", 100, result=result)
        finally:
            analysis_id_context.reset(token)
            current = self._get_job(analysis_id)
            if current:
                cleanup_upload_dir(current.upload_dir)

    def _get_job(self, analysis_id: str) -> AnalysisJob | None:
        with self._lock:
            return self._jobs.get(analysis_id)

    def _set_status(
        self,
        analysis_id: str,
        status: str,
        progress: int,
        result: RankingResponse | None = None,
        error: str | None = None,
    ) -> AnalysisJob | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if not job:
                return None
            job.status = status
            job.progress = progress
            job.result = result
            job.error = error
            job.updated_at = datetime.now(UTC)
            return job


analysis_job_manager = AnalysisJobManager()

# Role dans le projet:
# Ce fichier gere les analyses asynchrones en memoire. Les routes ranking l'utilisent pour creer, consulter et annuler des jobs.
