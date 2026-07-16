from __future__ import annotations

import json
from html import escape
from pathlib import Path


def render_report(result_path: Path, output_path: Path, extracted_texts: list[dict] | None = None) -> Path:
    data = json.loads(result_path.read_text(encoding="utf-8"))
    html = _build_html(data, extracted_texts or [])
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _build_html(data: dict, extracted_texts: list[dict]) -> str:
    extraction_section = _extracted_text_section(extracted_texts)
    if "detail" in data:
        body = f"""
        {extraction_section}
        <section class="error">
          <h2>Erreur</h2>
          <p>{escape(str(data["detail"]))}</p>
        </section>
        """
    else:
        job = data.get("job", {})
        ranking = data.get("ranking", [])
        rows, details = [], []
        for item in ranking:
            candidate = item.get("candidate", {})
            name = candidate.get("candidate_name") or candidate.get("filename") or "Candidat"
            score = float(candidate.get("final_score") or 0)
            rows.append(
                f"""
                <tr>
                  <td class="rank">{escape(str(item.get("rank_label") or item.get("rank")))}</td>
                  <td><strong>{escape(name)}</strong><br><span class="muted">{escape(candidate.get("filename", ""))}</span></td>
                  <td><span class="score {_score_class(score)}">{score:.2f}%</span></td>
                  <td>{escape("; ".join(candidate.get("strengths") or []) or "Aucune force majeure")}</td>
                  <td>{escape("; ".join(candidate.get("weaknesses") or []) or "Aucune faiblesse majeure")}</td>
                </tr>
                """
            )
            details.append(_candidate_detail(name, score, candidate))

        required_skills = job.get("required_skills") or {}
        body = f"""
        {extraction_section}
        <section class="card">
          <h2>Fiche de poste</h2>
          <p><strong>Poste :</strong> {escape(str(job.get("job_title") or "Non precise"))}</p>
          <div class="grid">
            <div><h3>Competences obligatoires</h3><ul>{_list_items(required_skills.get("mandatory"))}</ul></div>
            <div><h3>Competences souhaitees</h3><ul>{_list_items(required_skills.get("preferred"))}</ul></div>
            <div><h3>Responsabilites</h3><ul>{_list_items(job.get("responsibilities"))}</ul></div>
          </div>
        </section>
        <section class="card">
          <h2>Classement final</h2>
          <table>
            <thead><tr><th>Rang</th><th>Candidat</th><th>Score</th><th>Forces</th><th>Faiblesses</th></tr></thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </section>
        {"".join(details)}
        """

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Resultats SmartRecruit</title>
<style>
:root {{ font-family: Arial, sans-serif; color: #17211d; background: #f5f7f6; }}
body {{ margin: 0; padding: 32px; }}
header {{ max-width: 1180px; margin: 0 auto 22px; }}
h1 {{ margin: 0 0 6px; font-size: 32px; }}
.subtitle {{ color: #5b6862; }}
.card {{ max-width: 1180px; margin: 18px auto; background: white; border: 1px solid #dbe3df; border-radius: 8px; padding: 22px; box-shadow: 0 8px 24px rgba(0,0,0,.05); }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 14px; border-bottom: 1px solid #e5ebe8; vertical-align: top; }}
th {{ color: #52615a; font-size: 13px; text-transform: uppercase; }}
.rank {{ font-size: 22px; font-weight: 700; color: #1f7665; }}
.score {{ display: inline-block; min-width: 72px; padding: 7px 10px; border-radius: 6px; color: white; text-align: center; font-weight: 700; }}
.good {{ background: #1f8a5b; }} .mid {{ background: #b68122; }} .low {{ background: #8f3d32; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; }}
.muted {{ color: #66736d; font-size: 13px; }}
.cat {{ border: 1px solid #e3e9e6; border-radius: 8px; padding: 14px; margin: 12px 0; }}
.cat-head {{ display: flex; justify-content: space-between; font-weight: 700; }}
.bar {{ height: 9px; background: #e9eeeb; border-radius: 999px; overflow: hidden; margin: 10px 0; }}
.bar span {{ display:block; height:100%; }}
.cols {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; }}
h3 {{ margin-bottom: 8px; }} h4 {{ margin: 8px 0; color:#52615a; }}
ul {{ margin-top: 6px; padding-left: 20px; }}
.evidence li {{ margin-bottom: 14px; }}
.pill {{ display:inline-block; padding:4px 8px; background:#e2f2ed; color:#1f7665; border-radius:999px; font-size:12px; font-weight:700; }}
.pill.full {{ background:#dff3e8; color:#1f8a5b; }}
.pill.partial {{ background:#fff3d6; color:#946317; }}
.pill.none {{ background:#f8e1dd; color:#8f3d32; }}
.detail-cols {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5ebe8; }}
.mini-table {{ margin-top: 8px; font-size: 13px; }}
.mini-table th, .mini-table td {{ padding: 8px; }}
.error {{ max-width: 800px; margin: 40px auto; padding: 22px; background: #fff2f0; border: 1px solid #ffc7bd; border-radius: 8px; }}
.text-panel {{ margin: 14px 0; border: 1px solid #dfe7e3; border-radius: 8px; overflow: hidden; }}
details summary {{ cursor: pointer; padding: 14px; background: #f0f5f3; font-weight: 700; }}
.meta {{ display:flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }}
.meta span {{ background:#eef3f1; padding:6px 9px; border-radius:6px; color:#52615a; font-size:13px; }}
pre {{ margin: 0; padding: 16px; background: #101816; color: #e8f2ee; overflow: auto; white-space: pre-wrap; max-height: 520px; line-height: 1.45; }}
.sections {{ padding: 0 16px 16px; }}
.section-preview {{ border-left: 3px solid #1f7665; margin: 12px 0; padding-left: 10px; }}
</style>
</head>
<body>
<header>
  <h1>Resultats SmartRecruit</h1>
  <div class="subtitle">Classement lisible genere automatiquement apres l'analyse</div>
</header>
{body}
</body>
</html>"""


def _candidate_detail(name: str, score: float, candidate: dict) -> str:
    categories = []
    for category in candidate.get("category_scores", []):
        category_score = float(category.get("score") or 0)
        details = category.get("details") or {}
        extra_blocks = _category_extra_blocks(category.get("name", ""), details)
        categories.append(
            f"""
            <div class="cat">
              <div class="cat-head"><span>{escape(category.get("name", ""))}</span><b>{category_score:.2f}%</b></div>
              <div class="bar"><span class="{_score_class(category_score)}" style="width:{max(0, min(100, category_score))}%"></span></div>
              <div class="cols">
                <div><h4>Correspondances</h4><ul>{_list_items(category.get("matched"))}</ul></div>
                <div><h4>Manquants</h4><ul>{_list_items(category.get("missing"))}</ul></div>
              </div>
              {extra_blocks}
            </div>
            """
        )

    evidence = []
    for item in candidate.get("evidence", [])[:5]:
        evidence.append(
            f"""
            <li>
              <span class="pill">{escape(item.get("source", "preuve"))}</span>
              <span class="muted">score {float(item.get("score") or 0):.3f}</span>
              <p>{escape(item.get("text", "")[:450])}</p>
            </li>
            """
        )

    return f"""
    <section class="card">
      <h2>{escape(name)} <span class="score {_score_class(score)}">{score:.2f}%</span></h2>
      <div class="grid">
        <div><h3>Forces</h3><ul>{_list_items(candidate.get("strengths"))}</ul></div>
        <div><h3>Faiblesses</h3><ul>{_list_items(candidate.get("weaknesses"))}</ul></div>
      </div>
      <h3>Scores par critere</h3>
      {"".join(categories)}
      <h3>Preuves principales</h3>
      <ul class="evidence">{"".join(evidence) or '<li class="muted">Aucune preuve affichee</li>'}</ul>
    </section>
    """


def _category_extra_blocks(category_name: str, details: dict) -> str:
    if category_name == "technical_skills":
        return f"""
        <div class="cols detail-cols">
          <div><h4>Obligatoires trouves</h4><ul>{_list_items(details.get("matched_mandatory"))}</ul></div>
          <div><h4>Obligatoires manquants</h4><ul>{_list_items(details.get("missing_mandatory"))}</ul></div>
          <div><h4>Souhaites trouves</h4><ul>{_list_items(details.get("matched_preferred"))}</ul></div>
          <div><h4>Souhaites manquants</h4><ul>{_list_items(details.get("missing_preferred"))}</ul></div>
        </div>
        """
    if category_name == "responsibilities":
        responsibility_scores = details.get("responsibility_scores") or []
        rows = []
        for item in responsibility_scores:
            status = str(item.get("status") or "none")
            rows.append(
                f"""
                <tr>
                  <td><span class="pill {escape(status)}">{escape(status)}</span></td>
                  <td>{escape(str(item.get("responsibility") or ""))}</td>
                  <td>{float(item.get("score") or 0):.2f}%</td>
                  <td>{escape(str(item.get("evidence") or "")[:320])}</td>
                </tr>
                """
            )
        if not rows:
            return ""
        return f"""
        <h4>Evaluation detaillee des responsabilites</h4>
        <table class="mini-table">
          <thead><tr><th>Etat</th><th>Responsabilite</th><th>Score</th><th>Preuve</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
        """
    return ""


def _extracted_text_section(documents: list[dict]) -> str:
    if not documents:
        return ""
    panels = []
    for document in documents:
        sections = document.get("sections") or {}
        section_blocks = []
        for section_name, section_text in sections.items():
            preview = str(section_text).strip()
            if not preview:
                continue
            section_blocks.append(
                f"""
                <div class="section-preview">
                  <h4>{escape(str(section_name))}</h4>
                  <p>{escape(preview[:900])}</p>
                </div>
                """
            )
        panels.append(
            f"""
            <div class="text-panel">
              <details>
                <summary>{escape(document.get("label", "Document"))} - {escape(document.get("filename", ""))}</summary>
                <div class="sections">
                  <div class="meta">
                    <span>{int(document.get("char_count") or 0)} caracteres extraits</span>
                    <span>{len(sections)} sections detectees</span>
                  </div>
                  <h3>Sections detectees</h3>
                  {"".join(section_blocks) or '<p class="muted">Aucune section detectee.</p>'}
                  <h3>Texte brut extrait complet</h3>
                </div>
                <pre>{escape(str(document.get("text", "")))}</pre>
              </details>
            </div>
            """
        )
    return f"""
    <section class="card">
      <h2>Texte extrait des documents</h2>
      <p class="muted">Cette section montre le texte obtenu avant l'appel au modele et avant le scoring.</p>
      {"".join(panels)}
    </section>
    """


def _list_items(values: list | None) -> str:
    if not values:
        return '<span class="muted">Aucun</span>'
    return "".join(f"<li>{escape(str(value))}</li>" for value in values)


def _score_class(score: float) -> str:
    if score >= 70:
        return "good"
    if score >= 40:
        return "mid"
    return "low"
