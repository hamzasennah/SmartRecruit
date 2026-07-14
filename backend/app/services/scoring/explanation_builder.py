def build_strengths(category_scores) -> list[str]:
    return [f"{c.name}: forte correspondance." for c in category_scores if c.score >= 80][:5] or ["Aucun point fort majeur n'a ete detecte automatiquement."]


def build_weaknesses(category_scores) -> list[str]:
    return [f"{c.name}: insuffisant ({', '.join(c.missing[:3]) or 'preuves insuffisantes'})." for c in category_scores if c.score < 60][:5] or ["Pas de faiblesse critique selon les criteres extraits."]

