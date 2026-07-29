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
        errors_section = _errors_section(data.get("errors") or [])
        rows, details = [], []
        for item in ranking:
            candidate = item.get("candidate", {})
            name = candidate.get("candidate_name") or candidate.get("filename") or "Candidat"
            score = float(candidate.get("final_score") or 0)
            rows.append(
                f"""
                <tr>
                  <td class="rank-cell"><span class="rank">{escape(_rank_label(item))}</span></td>
                  <td class="candidate-cell"><strong>{escape(name)}</strong><span class="muted">{escape(candidate.get("filename", ""))}</span></td>
                  <td class="score-cell"><span class="score {_score_class(score)}">{score:.2f}%</span></td>
                  <td class="summary-cell"><ul class="compact-list">{_list_items(candidate.get("strengths") or ["Aucune force majeure"])}</ul></td>
                  <td class="summary-cell"><ul class="compact-list">{_list_items(candidate.get("weaknesses") or ["Aucune faiblesse majeure"])}</ul></td>
                </tr>
                """
            )
            details.append(_candidate_detail(name, score, candidate))

        required_skills = job.get("required_skills") or {}
        summary_section = _global_summary(ranking)
        body = f"""
        {extraction_section}
        {errors_section}
        {summary_section}
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
          <table class="ranking-table">
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
.notice {{ border-left: 4px solid #1f7665; }}
.verdict {{ padding: 12px 14px; background: #f0f5f3; border-radius: 6px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 14px; border-bottom: 1px solid #e5ebe8; vertical-align: top; }}
th {{ color: #52615a; font-size: 13px; text-transform: uppercase; }}
.ranking-table {{ table-layout: fixed; }}
.ranking-table th:nth-child(1), .ranking-table .rank-cell {{ width: 9%; }}
.ranking-table th:nth-child(2), .ranking-table .candidate-cell {{ width: 18%; }}
.ranking-table th:nth-child(3), .ranking-table .score-cell {{ width: 12%; }}
.ranking-table th:nth-child(4), .ranking-table .summary-cell {{ width: 29%; }}
.ranking-table th:nth-child(5), .ranking-table .summary-cell:last-child {{ width: 32%; }}
.ranking-table th, .ranking-table td {{ padding: 14px 12px; vertical-align: top; }}
.rank {{ display: inline-block; white-space: nowrap; font-size: 22px; line-height: 1.15; font-weight: 700; color: #1f7665; }}
.candidate-cell strong {{ display: block; line-height: 1.18; overflow-wrap: anywhere; }}
.candidate-cell .muted {{ display: block; margin-top: 4px; }}
.score-cell {{ white-space: nowrap; }}
.score {{ display: inline-block; min-width: 72px; padding: 7px 10px; border-radius: 6px; color: white; text-align: center; font-weight: 700; }}
.compact-list {{ display: grid; gap: 6px; list-style: none; margin: 0; padding: 0; line-height: 1.3; }}
.compact-list li {{ position: relative; margin: 0; padding-left: 16px; overflow-wrap: anywhere; }}
.compact-list li::before {{ position: absolute; top: .68em; left: 0; width: 4px; height: 4px; border-radius: 50%; background: #17241f; content: ""; transform: translateY(-50%); }}
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
              <p>{escape(_clean_snippet(item.get("text", ""), 450))}</p>
            </li>
            """
        )

    return f"""
    <section class="card">
      <h2>{escape(name)} <span class="score {_score_class(score)}">{score:.2f}%</span></h2>
      <p class="verdict"><strong>Verdict automatique :</strong> {escape(_candidate_verdict(score, candidate))}</p>
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
          <div><h4>Obligatoires partiels</h4><ul>{_list_items(_partial_skill_labels(details.get("partial_mandatory") or []))}</ul></div>
          <div><h4>Obligatoires manquants</h4><ul>{_list_items(details.get("missing_mandatory"))}</ul></div>
          <div><h4>Souhaites trouves</h4><ul>{_list_items(details.get("matched_preferred"))}</ul></div>
          <div><h4>Souhaites partiels</h4><ul>{_list_items(_partial_skill_labels(details.get("partial_preferred") or []))}</ul></div>
          <div><h4>Souhaites manquants</h4><ul>{_list_items(details.get("missing_preferred"))}</ul></div>
        </div>
        """
    if category_name == "responsibilities":
        responsibility_scores = details.get("responsibility_scores") or []
        partial_labels = _partial_responsibility_labels(details)
        partial_block = (
            f"""
            <h4>Responsabilites partiellement prouvees</h4>
            <ul>{_list_items(partial_labels)}</ul>
            """
            if partial_labels
            else ""
        )
        rows = []
        for item in responsibility_scores:
            status = str(item.get("status") or "none")
            rows.append(
                f"""
                <tr>
                  <td><span class="pill {escape(status)}">{escape(_status_label(status))}</span></td>
                  <td>{escape(str(item.get("responsibility") or ""))}</td>
                  <td>{float(item.get("score") or 0):.2f}%</td>
                  <td>{escape(_clean_snippet(str(item.get("evidence") or ""), 320))}</td>
                </tr>
                """
            )
        if not rows:
            return partial_block
        return f"""
        {partial_block}
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
                {_raw_text_block(document)}
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


def _raw_text_block(document: dict) -> str:
    if document.get("raw_text_included"):
        return f"<pre>{escape(str(document.get('text', '')))}</pre>"
    return (
        '<div class="sections">'
        '<p class="muted">Texte brut masque par defaut pour proteger les donnees personnelles. '
        "Relancer le script avec --include-raw-text uniquement dans un contexte local controle.</p>"
        "</div>"
    )


def _errors_section(errors: list[str]) -> str:
    if not errors:
        return ""
    return f"""
    <section class="error">
      <h2>Erreurs de traitement</h2>
      <p>Certains documents ont ete lus, mais leur analyse structuree n'a pas pu etre terminee.</p>
      <ul>{_list_items(errors)}</ul>
    </section>
    """


def _global_summary(ranking: list[dict]) -> str:
    scores = [
        float((item.get("candidate") or {}).get("final_score") or 0)
        for item in ranking
    ]
    if not scores:
        return ""
    best = max(scores)
    if best < 40:
        message = (
            "Aucun candidat ne presente une correspondance forte avec la fiche. "
            "Le classement indique les profils les moins eloignes des criteres extraits."
        )
    elif best < 70:
        message = (
            "Le meilleur profil reste partiel. Les preuves et les criteres manquants doivent etre verifies."
        )
    else:
        message = "Au moins un candidat presente une correspondance forte selon les criteres extraits."
    return f"""
    <section class="card notice">
      <h2>Synthese automatique</h2>
      <p>{escape(message)}</p>
      <p class="muted">Cette synthese ne modifie pas les scores. Elle interprete uniquement le score maximal du classement.</p>
    </section>
    """


def _candidate_verdict(score: float, candidate: dict) -> str:
    technical = _category(candidate, "technical_skills")
    responsibilities = _category(candidate, "responsibilities")
    if score < 40:
        if technical and (technical.get("details") or {}).get("matched_mandatory"):
            return "Correspondance faible, avec quelques criteres obligatoires prouves mais insuffisants pour une forte compatibilite."
        if responsibilities and float(responsibilities.get("score") or 0) > 0:
            return "Correspondance faible, avec quelques responsabilites partiellement proches mais peu de preuves directes."
        return "Correspondance faible avec les criteres extraits de la fiche."
    if score < 70:
        return "Correspondance partielle. Le profil doit etre verifie manuellement sur les criteres manquants."
    return "Correspondance forte selon les criteres extraits, sous reserve de validation humaine."


def _category(candidate: dict, name: str) -> dict | None:
    for category in candidate.get("category_scores", []):
        if category.get("name") == name:
            return category
    return None


def _status_label(status: str) -> str:
    return {
        "full": "exact",
        "partial": "partiel",
        "none": "absent",
    }.get(status, status)


def _clean_snippet(value: str, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:") + "..."


def _rank_label(item: dict) -> str:
    label = str(item.get("rank_label") or item.get("rank") or "")
    return label.replace("ex aequo", "ex æquo")


def _list_items(values: list | None) -> str:
    if not values:
        return '<span class="muted">Aucun</span>'
    return "".join(f"<li>{escape(str(value))}</li>" for value in values)


def _partial_skill_labels(values: list) -> list[str]:
    labels: list[str] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        credit = item.get("credit_percent")
        suffix = f" - credit {float(credit):.0f}%" if isinstance(credit, (int, float)) else ""
        if skill and evidence:
            labels.append(f"{skill} via {evidence}{suffix}")
        elif skill:
            labels.append(skill)
    return labels


def _partial_responsibility_labels(details: dict) -> list[str]:
    labels: list[str] = []
    for item in details.get("responsibility_scores") or []:
        if not isinstance(item, dict) or item.get("status") != "partial":
            continue
        responsibility = str(item.get("responsibility") or "").strip()
        score = item.get("score")
        suffix = f" ({float(score):.0f}%)" if isinstance(score, (int, float)) else ""
        if responsibility:
            labels.append(f"{responsibility}{suffix}")
    if labels:
        return list(dict.fromkeys(labels))
    return [str(item) for item in details.get("partial") or [] if str(item).strip()]


def _score_class(score: float) -> str:
    if score >= 70:
        return "good"
    if score >= 40:
        return "mid"
    return "low"

# Role dans le projet:
# Ce script transforme un resultat JSON en rapport lisible. Il sert a inspecter hors frontend les sorties du classement.
