import os
from pathlib import Path

import pytest

from app.dependencies import get_batch_ranking_pipeline


pytestmark = pytest.mark.skipif(
    os.getenv("SMARTRECRUIT_RUN_INTEGRATION") != "1",
    reason="Integration test requires live Qwen endpoints and PostgreSQL.",
)


def test_batch_ranking_pipeline_with_text_files(tmp_path: Path) -> None:
    job = tmp_path / "job.txt"
    job.write_text("Data Analyst. Python SQL Power BI. 2 ans experience. analyser les donnees et construire des dashboards.", encoding="utf-8")
    good = tmp_path / "good_cv.txt"
    good.write_text("Hamza Data Analyst\nData Analyst - janvier 2022 a decembre 2024\nPython SQL PowerBI dashboards.", encoding="utf-8")
    weak = tmp_path / "weak_cv.txt"
    weak.write_text("Profil general communication vente.", encoding="utf-8")

    response = get_batch_ranking_pipeline().run(job, [good, weak])

    assert response.total_candidates == 2
    assert response.ranking[0].candidate.final_score >= response.ranking[1].candidate.final_score
