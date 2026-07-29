from __future__ import annotations

import re

from app.services.normalization.text_normalizer import normalize_text

SECTION_PATTERNS = {"skills": r"(competences|skills|technologies|outils)", "experience": r"(experience|experiences professionnelles|work experience)", "education": r"(formation|education|diplome)", "languages": r"(langues|languages)", "certifications": r"(certifications|certificats)", "projects": r"(projets|projects)", "responsibilities": r"(missions|responsabilites|responsibilities)", "requirements": r"(profil recherche|exigences|requirements)"}


def segment_sections(text: str) -> dict[str, str]:
    lines = [line.strip() for line in re.split(r"[\n\r]+", text) if line.strip()]
    sections: dict[str, list[str]] = {}
    current = "unclassified"
    for line in lines:
        section = _section_for_line(line)
        if section:
            # Section names drive RAG filtering later, so detection is kept to
            # short heading-like lines rather than arbitrary body text.
            current = section
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(line)
    compact = {"full_text": text}
    compact.update({key: "\n".join(value).strip() for key, value in sections.items() if "\n".join(value).strip()})
    return compact


def _section_for_line(line: str) -> str | None:
    normalized = normalize_text(line)
    if len(normalized) > 80:
        # Long lines are usually content, not headings.
        return None
    for section, pattern in SECTION_PATTERNS.items():
        if re.fullmatch(pattern, normalized) or re.search(rf"\b{pattern}\b", normalized):
            return section
    return None

# Role dans le projet:
# Ce fichier segmente le texte en sections heuristiques. Le retrieval et l'affichage des preuves utilisent ces sections pour filtrer le contexte.
