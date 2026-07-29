from __future__ import annotations

import json

from scripts.render_result_report import render_report


def test_report_masks_raw_text_by_default(tmp_path) -> None:
    result = tmp_path / "result.json"
    output = tmp_path / "report.html"
    result.write_text(
        json.dumps(
            {
                "job": {"job_title": "Data Analyst", "required_skills": {}, "responsibilities": []},
                "ranking": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )

    render_report(
        result,
        output,
        extracted_texts=[
            {
                "label": "CV 1",
                "filename": "candidate.txt",
                "char_count": 24,
                "text": "",
                "raw_text_included": False,
                "sections": {"full_text": "Sensitive candidate text"},
            }
        ],
    )

    html = output.read_text(encoding="utf-8")
    assert "Texte brut masque par defaut" in html
    assert "<pre>Sensitive candidate text</pre>" not in html

# Role dans le projet:
# Ce fichier contient les tests unitaires pour reports privacy. Il protege le comportement existant pendant les refactors sans appeler les services externes.
