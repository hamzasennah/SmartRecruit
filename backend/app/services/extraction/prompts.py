EXTRACTION_RULES = """
REGLES D'EXTRACTION:
- Retourne uniquement un JSON valide. Aucun markdown, aucun commentaire, aucune explication.
- Utilise exactement les champs du schema demande, sans ajouter d'autres cles.
- Utilise null pour une chaine inconnue et [] pour une liste inconnue.
- Toutes les listes de competences, outils, langues, responsabilites, missions, titres, domaines et certifications doivent contenir uniquement des chaines simples, jamais des objets.
- N'invente pas, ne complete pas, ne traduis pas et n'enrichis pas les faits absents du texte.
- Chaque competence, outil, entreprise, poste, date, certification, langue, diplome, ecole et projet doit avoir une preuve directe dans le texte.
- N'extrais une competence que si le terme exact ou un synonyme explicitement ecrit apparait.
- N'infere jamais Python depuis "backend", SQL depuis "base de donnees", AWS/Azure depuis "cloud", Power BI depuis "dashboard", ni une competence depuis une responsabilite.
- Ne mets jamais les langues humaines dans les competences.
- Ne cree pas d'experience depuis la formation, les certifications, les projets personnels ou le resume general.
- Ne compte pas les stages, PFE, internships ou periodes stagiaire comme experiences professionnelles.
- Ne transforme pas une responsabilite ou une mission en competence si l'outil n'est pas explicitement cite.
- Preserve les dates telles qu'elles sont ecrites. Si une date est absente ou incertaine, utilise null.
- Si le texte est en francais, garde les noms, intitules, diplomes et entreprises tels qu'ils sont ecrits.
- Garde les competences atomiques: "Python", "Power BI", "PostgreSQL" plutot que des phrases longues.
- Si un terme est explicitement ecrit au pluriel, garde sa forme atomique canonique: "KPIs" -> "KPI", "dashboards" -> "dashboard".
- Les missions et descriptions doivent etre courtes, factuelles, et limitees a 160 caracteres.
"""

# The prompts ask the LLM for structured evidence only. The wording deliberately
# forbids scoring and invention so deterministic matchers can own ranking logic,
# but model compliance is still verified again in coercion/validation code.
CV_EXTRACTION_PROMPT = (
    EXTRACTION_RULES
    + """
Tu es un parseur RH strict. Extrais uniquement les informations visibles dans le CV.
Ne calcule pas de score, de duree totale, de pertinence ou de confiance.
Les stages, PFE, internships et periodes stagiaire ne vont pas dans experiences.
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
      "missions": [],
      "skills_used": []
    }}
  ],
  "education": [
    {{
      "degree": null,
      "normalized_level": null,
      "field": null,
      "institution": null,
      "start_year": null,
      "end_year": null
    }}
  ],
  "languages": [
    {{"language": "", "normalized_level": null}}
  ],
  "certifications": [],
  "projects": [
    {{"name": null, "description": null, "skills_used": []}}
  ]
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
Les langues humaines, meme avec un niveau comme "fluent French" ou "anglais courant", vont uniquement dans language_requirements.
Les responsabilites doivent etre des actions/metiers a realiser, pas des outils ni un intitule de poste.
Ne calcule aucun score et ne juge aucun candidat.
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
  "responsibilities": []
}}

FICHE DE POSTE:
{text}
"""
)

# Role dans le projet:
# Ce fichier contient les prompts d'extraction. Il maintient les consignes LLM separees du code de validation et de scoring.
