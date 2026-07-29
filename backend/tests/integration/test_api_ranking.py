import os

import pytest
from app.main import app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.getenv("SMARTRECRUIT_RUN_INTEGRATION") != "1",
    reason="Integration test requires NVIDIA API and PostgreSQL.",
)


def test_ranking_endpoint_with_text_uploads() -> None:
    os.environ.setdefault("SMARTRECRUIT_API_KEY", "integration-test-key")
    files = [
        (
            "job_file",
            (
                "job.txt",
                b"Data Analyst. Python SQL Power BI. 2 ans experience. analyser les donnees et construire des dashboards.",
                "text/plain",
            ),
        ),
        (
            "cv_files",
            (
                "good.txt",
                b"Hamza Data Analyst\nData Analyst - janvier 2022 a decembre 2024\nPython SQL PowerBI dashboards.",
                "text/plain",
            ),
        ),
        (
            "cv_files",
            ("weak.txt", b"Profil general communication vente.", "text/plain"),
        ),
    ]
    with TestClient(app) as client:
        response = client.post(
            "/api/ranking/analyze",
            headers={"X-API-Key": os.environ["SMARTRECRUIT_API_KEY"]},
            files=files,
            data={"top_k": "3"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] == 2
    assert payload["ranking"][0]["candidate"]["final_score"] >= payload["ranking"][1]["candidate"]["final_score"]

# Role dans le projet:
# Ce fichier couvre l'analyse ranking via API avec dependances externes. Il reste separe et conditionnel car NVIDIA/PostgreSQL sont requis.
