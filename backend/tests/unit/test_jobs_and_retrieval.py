from __future__ import annotations

import time

from app.api.routes import ranking
from app.core.security import rate_limiter
from app.main import app
from app.schemas.job import StructuredJobDescription
from app.schemas.ranking import RankingResponse
from app.services.documents.section_segmenter import segment_sections
from app.services.orchestration.job_manager import analysis_job_manager
from app.services.retrieval.section_indexer import SectionIndexer
from fastapi.testclient import TestClient


class FakePipeline:
    def run(self, job_path, cv_paths, top_k: int = 5) -> RankingResponse:
        return RankingResponse(job=StructuredJobDescription(job_title="Data Analyst"), total_candidates=len(cv_paths))


def _files() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("job_file", ("job.txt", b"Data Analyst\nPython", "text/plain")),
        ("cv_files", ("cv.txt", b"Candidate Python", "text/plain")),
    ]


def test_ranking_job_lifecycle(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRECRUIT_API_KEY", "job-secret")
    monkeypatch.setenv("RATE_LIMIT_REQUESTS", "1")
    monkeypatch.setenv("MAX_CV_FILES", "20")
    rate_limiter.reset()
    analysis_job_manager.reset()
    monkeypatch.setattr(ranking, "get_batch_ranking_pipeline", lambda: FakePipeline())

    with TestClient(app) as client:
        created = client.post(
            "/api/ranking/jobs",
            headers={"X-API-Key": "job-secret"},
            files=_files(),
            data={"top_k": "3"},
        )
        assert created.status_code == 202
        analysis_id = created.json()["analysis_id"]

        payload = None
        for _ in range(20):
            status = client.get(f"/api/ranking/jobs/{analysis_id}", headers={"X-API-Key": "job-secret"})
            assert status.status_code == 200
            payload = status.json()
            if payload["status"] == "completed":
                break
            time.sleep(0.05)

    assert payload is not None
    assert payload["status"] == "completed"
    assert payload["progress"] == 100
    assert payload["result"]["total_candidates"] == 1


def test_segment_sections_keeps_full_text_complete() -> None:
    text = "Intro line\nSkills\nPython\nExperience\nData Analyst"

    sections = segment_sections(text)

    assert sections["full_text"] == text
    assert sections["skills"] == "Python"
    assert sections["experience"] == "Data Analyst"
    assert sections["unclassified"] == "Intro line"


def test_section_indexer_batches_embeddings(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "2")

    class Embeddings:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def embed_passages(self, texts: list[str]) -> list[list[float]]:
            self.calls.append(texts)
            return [[float(index), 1.0] for index, _ in enumerate(texts)]

    class Store:
        def __init__(self) -> None:
            self.upserts = 0

        def upsert(self, namespace: str, chunks: list[dict], vectors: list[list[float]]) -> None:
            self.upserts += 1
            assert len(chunks) == len(vectors)

    embeddings = Embeddings()
    store = Store()
    indexer = SectionIndexer(embeddings, store)

    chunks = indexer.index_sections(
        "ns",
        "doc",
        {
            "full_text": "a " * 1200,
            "skills": "Python SQL",
            "experience": "Data Analyst",
        },
    )

    assert len(chunks) > 2
    assert all(len(call) <= 2 for call in embeddings.calls)
    assert store.upserts == len(embeddings.calls)
