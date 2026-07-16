EXTRACTION_RULES = """
REGLES D'EXTRACTION:
- Retourne uniquement un JSON valide. Aucun markdown, aucun commentaire, aucune explication.
- Retourne un JSON compact et ferme toujours toutes les accolades et tous les crochets.
- Utilise null pour une chaine inconnue et [] pour une liste inconnue.
- N'invente pas, ne complete pas, ne traduis pas et n'enrichis pas les faits absents du texte.
- Chaque competence, outil, entreprise, poste, date, certification, langue, diplome, ecole et projet doit avoir une preuve directe dans le texte.
- N'extrais une competence que si le terme exact ou un synonyme explicitement ecrit apparait.
- N'infere jamais Python depuis "backend", SQL depuis "base de donnees", AWS/Azure depuis "cloud", Power BI depuis "dashboard", ni une competence depuis une responsabilite.
- Chaque mission doit etre une chaine de caracteres courte, jamais un objet JSON imbrique.
- Garde les competences atomiques: "Python", "Power BI", "PostgreSQL" plutot que longues phrases.
- Ne mets jamais les langues humaines dans les competences.
- Ne cree pas d'experience depuis la formation, les certifications, les projets personnels ou le resume general.
- Ne transforme pas une responsabilite ou une mission en competence si l'outil n'est pas explicitement cite.
- Preserve les dates telles qu'elles sont ecrites. Si une date est absente ou incertaine, utilise null.
- Si le texte est en francais, garde les noms, intitules et diplomes tels qu'ils sont ecrits.
- Limite les listes longues aux elements les plus importants et directement prouves.
- Les champs texte doivent etre courts: une mission ou description ne depasse pas 160 caracteres.
"""

CV_EXTRACTION_PROMPT = (
    EXTRACTION_RULES
    + """
Tu es un parseur RH strict. Extrais uniquement les informations visibles dans le CV.
Selectionne les informations utiles au recrutement sans recopier tout le CV:
- maximum 20 competences techniques, 12 outils, 8 soft skills;
- maximum 8 experiences professionnelles;
- maximum 3 missions courtes par experience;
- maximum 4 formations;
- maximum 4 projets.

SCHEMA JSON OBLIGATOIRE:
{{
  "candidate_name": null,
  "job_titles": [],
  "skills": {{"technical": [], "soft": [], "tools": []}},
  "experiences": [
    {{
      "job_title": null,
      "company": null,
      "start_date": null,
      "end_date": null,
      "declared_duration": null,
      "duration_months": null,
      "missions": [],
      "skills_used": [],
      "relevance_score": 0.0,
      "confidence": 0.0
    }}
  ],
  "education": [
    {{
      "degree": null,
      "normalized_level": null,
      "field": null,
      "institution": null,
      "start_year": null,
      "end_year": null,
      "confidence": 0.0
    }}
  ],
  "languages": [
    {{"language": "", "level": null, "normalized_level": null, "confidence": 0.0, "estimated": false}}
  ],
  "certifications": [],
  "projects": [
    {{"name": null, "description": null, "skills_used": []}}
  ],
  "raw_text_preview": "",
  "extraction_confidence": 0.0
}}

CV:
{text}
"""
)

JOB_EXTRACTION_PROMPT = (
    EXTRACTION_RULES
    + """
Tu es un parseur RH strict de fiche de poste. Extrais seulement les criteres utiles au matching candidat.
Separe clairement les competences obligatoires, les competences souhaitees et les soft skills.
Les responsabilites doivent etre des actions/metiers a realiser, pas des outils ni un intitule de poste.
Limite les responsabilites a 8 elements maximum.

SCHEMA JSON OBLIGATOIRE:
{{
  "job_title": null,
  "required_skills": {{"mandatory": [], "preferred": [], "soft": []}},
  "experience_requirements": {{
    "minimum_months": 0,
    "preferred_job_titles": [],
    "required_domains": []
  }},
  "education_requirements": {{"minimum_level": null, "accepted_fields": []}},
  "language_requirements": [
    {{"language": "", "minimum_level": null}}
  ],
  "certifications": [],
  "responsibilities": [],
  "raw_text_preview": "",
  "extraction_confidence": 0.0
}}

FICHE DE POSTE:
{text}
"""
)
