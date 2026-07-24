from __future__ import annotations

from pathlib import Path

from app.api.routes import ranking
from app.core.security import rate_limiter
from app.main import app
from app.schemas.job import StructuredJobDescription
from app.schemas.ranking import RankingResponse
from fastapi.testclient import TestClient


class FakePipeline:
    def __init__(self) -> None:
        self.seen_job = None
        self.seen_cvs = []

    def run(self, job_path, cv_paths, top_k: int = 5) -> RankingResponse:
        self.seen_job = job_path
        self.seen_cvs = cv_paths
        return RankingResponse(job=StructuredJobDescription(job_title="Data Analyst"), total_candidates=0)


def _files(cv_count: int = 1, cv_payload: bytes = b"Candidate") -> list[tuple[str, tuple[str, bytes, str]]]:
    files: list[tuple[str, tuple[str, bytes, str]]] = [
        ("job_file", ("job.txt", b"Data Analyst\nPython", "text/plain")),
    ]
    for index in range(cv_count):
        files.append(("cv_files", (f"cv{index}.txt", cv_payload, "text/plain")))
    return files


def test_ranking_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "secret")
    rate_limiter.reset()

    with TestClient(app) as client:
        response = client.post("/api/ranking/analyze", files=_files(), data={"top_k": "3"})

    assert response.status_code == 401


def test_ranking_rejects_when_auth_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("SMARTRECRUIT_API_KEY", raising=False)
    rate_limiter.reset()

    with TestClient(app) as client:
        response = client.post("/api/ranking/analyze", files=_files(), data={"top_k": "3"})

    assert response.status_code == 503


def test_ranking_enforces_cv_quota_before_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "quota-secret")
    monkeypatch.setenv("MAX_CV_FILES", "1")
    rate_limiter.reset()
    fake = FakePipeline()
    monkeypatch.setattr(ranking, "get_batch_ranking_pipeline", lambda: fake)

    with TestClient(app) as client:
        response = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": "quota-secret"},
            files=_files(cv_count=2),
            data={"top_k": "3"},
        )

    assert response.status_code == 413
    assert fake.seen_job is None


def test_ranking_enforces_upload_size(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "size-secret")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "4")
    monkeypatch.setenv("MAX_CV_FILES", "20")
    rate_limiter.reset()

    with TestClient(app) as client:
        response = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": "size-secret"},
            files=_files(),
            data={"top_k": "3"},
        )

    assert response.status_code == 413
    assert response.json()["detail"] == "Fichier trop volumineux."


def test_ranking_saves_random_files_and_cleans_upload_dir(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "clean-secret")
    monkeypatch.delenv("MAX_UPLOAD_BYTES", raising=False)
    monkeypatch.setenv("MAX_CV_FILES", "20")
    rate_limiter.reset()
    fake = FakePipeline()
    monkeypatch.setattr(ranking, "get_batch_ranking_pipeline", lambda: fake)

    uploads_root = Path("backend/uploads")
    before = {path.name for path in uploads_root.glob("analysis_*")}
    with TestClient(app) as client:
        response = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": "clean-secret"},
            files=_files(cv_count=1),
            data={"top_k": "3"},
        )
    after = {path.name for path in uploads_root.glob("analysis_*")}

    assert response.status_code == 200
    assert before == after
    assert fake.seen_job.original_filename == "job.txt"
    assert fake.seen_job.path.name.startswith("job_")
    assert fake.seen_job.path.name.endswith(".txt")
    assert fake.seen_cvs[0].original_filename == "cv0.txt"


def test_ranking_rate_limit(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "rate-secret")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
    monkeypatch.setenv("MAX_CV_FILES", "20")
    rate_limiter.reset()
    monkeypatch.setattr(ranking, "get_batch_ranking_pipeline", lambda: FakePipeline())

    with TestClient(app) as client:
        first = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": "rate-secret"},
            files=_files(),
            data={"top_k": "3"},
        )
        second = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": "rate-secret"},
            files=_files(),
            data={"top_k": "3"},
        )

    assert first.status_code == 200
    assert second.status_code == 429
