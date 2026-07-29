def build_strengths(category_scores) -> list[str]:
    strengths: list[str] = []
    by_name = {score.name: score for score in category_scores}

    technical = by_name.get("technical_skills")
    if technical:
        details = technical.details or {}
        matched_mandatory = details.get("matched_mandatory") or []
        matched_preferred = details.get("matched_preferred") or []
        partial_mandatory = details.get("partial_mandatory") or []
        if matched_mandatory:
            strengths.append(f"Competences obligatoires trouvees: {_join_items(matched_mandatory[:5])}.")
        if partial_mandatory:
            strengths.append(f"Competences obligatoires partiellement prouvees: {_join_items(_partial_skill_labels(partial_mandatory)[:4])}.")
        if matched_preferred:
            strengths.append(f"Competences souhaitees trouvees: {_join_items(matched_preferred[:5])}.")

    responsibilities = by_name.get("responsibilities")
    if responsibilities:
        details = responsibilities.details or {}
        partial = details.get("partial") or []
        if responsibilities.matched:
            strengths.append(f"Responsabilites prouvees: {_join_items(responsibilities.matched[:3])}.")
        if partial:
            strengths.append(f"Responsabilites partiellement prouvees: {_join_items(partial[:3])}.")

    for score in category_scores:
        if score.name in {"technical_skills", "responsibilities"}:
            continue
        if score.score >= 80 and score.matched:
            strengths.append(f"{_label(score.name)}: {_join_items(score.matched[:3])}.")

    return strengths[:5] or ["Aucun point fort majeur prouve par les criteres extraits."]


def build_weaknesses(category_scores) -> list[str]:
    weaknesses: list[str] = []
    by_name = {score.name: score for score in category_scores}

    technical = by_name.get("technical_skills")
    if technical:
        details = technical.details or {}
        missing_mandatory = details.get("missing_mandatory") or []
        partial_mandatory = details.get("partial_mandatory") or []
        if missing_mandatory:
            weaknesses.append(f"Competences obligatoires manquantes: {_join_items(missing_mandatory[:6])}.")
        if partial_mandatory:
            weaknesses.append(f"Competences obligatoires incompletes: {_join_items(_partial_skill_labels(partial_mandatory)[:4])}.")

    responsibilities = by_name.get("responsibilities")
    if responsibilities and responsibilities.score < 60:
        if responsibilities.missing:
            weaknesses.append(f"Responsabilites sans preuve directe: {_join_items(responsibilities.missing[:3])}.")

    soft = by_name.get("soft_skills")
    if soft and soft.score < 60 and soft.missing:
        weaknesses.append(f"Soft skills manquants: {_join_items(soft.missing[:4])}.")

    experience = by_name.get("experience")
    if experience and experience.score < 60 and experience.missing:
        weaknesses.append(f"Experience pertinente insuffisante: {_join_items(experience.missing[:2])}.")

    return weaknesses[:5] or ["Pas de faiblesse critique selon les criteres extraits."]


def _label(name: str) -> str:
    labels = {
        "education": "Formation",
        "experience": "Experience",
        "languages": "Langues",
        "soft_skills": "Soft skills",
    }
    return labels.get(name, name)


def _join_items(values: list[str]) -> str:
    return ", ".join(str(value).strip(" .;:") for value in values if str(value).strip())


def _partial_skill_labels(values: list[dict]) -> list[str]:
    labels: list[str] = []
    for item in values:
        skill = str(item.get("skill") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        if skill and evidence:
            labels.append(f"{skill} via {evidence}")
        elif skill:
            labels.append(skill)
    return labels


# Role dans le projet:
# Ce fichier transforme les scores par categorie en forces/faiblesses. Le moteur de scoring l'utilise pour rendre le classement explicable.
