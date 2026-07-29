import pytest
from app.schemas.cv import Experience, SkillSet, StructuredCV
from app.schemas.document import DocumentText
from app.schemas.job import RequiredSkills, StructuredJobDescription
from app.services.extraction.cv_extractor import CVExtractor, enrich_cv_with_job_skill_evidence
from app.services.extraction.job_extractor import JobExtractor
from app.services.scoring.scoring_engine import ScoringEngine


class StaticLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate_json(self, prompt: str) -> dict:
        return self.payload


def test_job_extractor_cleans_realistic_job_sheet_responsibilities() -> None:
    text = """
    Data Analyst packaging tool (SPM)
    Mission : BI/Data project management for SPM project
    create and enhance dashbord for SPM project
    Tools : Power BI, Excel et eventually Foundry
    Data available in datalake Snowflake + Azure
    lead data workstream with ITMS to clarify business needs
    by IT solution in terms of data and KPI/dashboard:
    Availability of data in Snowflake
    Creation of KPI / dashbord in Power BI or Foundry
    First experience in data analysis is required.
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Data Analyst packaging tool (SPM)",
        "required_skills": {
            "mandatory": ["Power BI", "Excel", "dashboard", "KPI", "Snowflake", "Azure"],
            "preferred": ["Foundry", "project management", "business needs"],
            "soft": [],
        },
        "experience_requirements": {"minimum_months": 12},
        "responsibilities": [
            "Data Analyst packaging tool (SPM)",
            "Tools : Power BI, Excel et eventually Foundry",
            "by IT solution in terms of data and KPI/dashboard:",
        ],
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.required_skills.mandatory == ["power bi", "excel", "dashboard", "kpi", "snowflake", "azure"]
    assert job.required_skills.preferred == ["foundry", "project management", "business needs", "spm", "itms"]
    assert job.experience_requirements.minimum_months == 12
    assert job.responsibilities == [
        "Creer et ameliorer les tableaux de bord et KPI.",
        "Piloter le workstream BI/Data.",
        "Clarifier les besoins metiers et assurer leur couverture.",
        "Garantir la disponibilite des donnees dans Snowflake/Azure.",
    ]


def test_job_extractor_moves_languages_out_of_technical_skills_and_infers_title() -> None:
    text = """
    Sensitivity: C1-Internal
    Data analyst packaging tool (SPM)
    Skills:
    fluent French & English
    excel power bi and snowflake are a must, foundry would be good
    autonomy (leadership, self-driven) is a must
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": None,
        "required_skills": {
            "mandatory": ["Power BI", "Excel", "Snowflake", "French", "English"],
            "preferred": ["Foundry"],
            "soft": ["fluent French", "fluent English", "project management"],
        },
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.job_title == "Data analyst packaging tool (SPM)"
    assert job.required_skills.mandatory == ["power bi", "excel", "snowflake"]
    assert job.required_skills.preferred == ["foundry", "spm"]
    assert job.required_skills.soft == ["autonomy", "leadership", "self driven"]
    assert [language.language for language in job.language_requirements] == ["francais", "anglais"]


def test_job_extractor_never_keeps_language_level_phrases_as_soft_skills() -> None:
    text = """
    Data Analyst
    Skills:
    fluent French, fluent English
    autonomy and leadership
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Data Analyst",
        "required_skills": {
            "mandatory": [],
            "preferred": [],
            "soft": ["fluent French", "fluent English", "Autonomy", "Leadership"],
        },
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.required_skills.soft == ["autonomy", "leadership"]
    assert [language.language for language in job.language_requirements] == ["francais", "anglais"]


def test_job_extractor_removes_model_skills_not_proven_in_job_text() -> None:
    text = """
    Data analyst packaging tool (SPM)
    Tools : Power BI, Excel et eventually Foundry
    Data available in datalake Snowflake + Azure
    Creation of KPI / dashbord in Power BI or Foundry
    fluent French & English
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Data analyst",
        "required_skills": {
            "mandatory": ["Python", "Power BI", "PostgreSQL", "Excel", "Snowflake"],
            "preferred": ["Django", "Foundry"],
            "soft": [],
        },
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert "python" not in job.required_skills.mandatory
    assert "postgresql" not in job.required_skills.mandatory
    assert "django" not in job.required_skills.preferred
    assert job.required_skills.mandatory == ["power bi", "excel", "snowflake", "dashboard", "kpi", "azure"]
    assert job.required_skills.preferred == ["foundry", "spm"]


def test_job_extractor_uses_bounded_technical_signals() -> None:
    text = """
    Developpeur Frontend
    Stack obligatoire : JavaScript, React, HTML et CSS.
    """
    document = DocumentText(filename="frontend.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Developpeur Frontend",
        "required_skills": {"mandatory": [], "preferred": [], "soft": []},
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert "javascript" in job.required_skills.mandatory
    assert "java" not in job.required_skills.mandatory


@pytest.mark.parametrize(
    "case",
    [
        {
            "name": "backend",
            "cv_title": "Developpeur Backend",
            "job_title": "Developpeur Backend",
            "cv_text": """
            Nadia Backend
            Developpeur Backend Java Spring Boot.
            API REST, Docker, Kubernetes, PostgreSQL, Git et CI/CD.
            """,
            "job_text": """
            Developpeur Backend
            Competences obligatoires : Java, Spring Boot, API REST, Docker, PostgreSQL, Git.
            """,
            "expected_cv_skills": {"java", "spring boot", "api rest", "docker", "kubernetes", "postgresql", "git", "ci cd"},
            "expected_job_skills": {"java", "spring boot", "api rest", "docker", "postgresql", "git"},
            "minimum_score": 95.0,
        },
        {
            "name": "support",
            "cv_title": "Support IT",
            "job_title": "Technicien Support IT",
            "cv_text": """
            Yassine Support IT
            Support utilisateurs ITIL avec ServiceNow, gestion de tickets, Active Directory et Office 365.
            Administration Windows Server et Linux, reseaux TCP/IP, DNS, DHCP, VPN, firewall, SLA et gestion des incidents.
            """,
            "job_text": """
            Technicien Support IT
            Requis : ITIL, ticketing ServiceNow, Active Directory, Office 365, networking, DNS, DHCP, VPN, incident management.
            """,
            "expected_cv_skills": {
                "itil",
                "ticketing",
                "servicenow",
                "active directory",
                "office 365",
                "windows server",
                "linux",
                "networking",
                "tcp ip",
                "dns",
                "dhcp",
                "vpn",
                "firewall",
                "sla",
                "incident management",
            },
            "expected_job_skills": {
                "itil",
                "ticketing",
                "servicenow",
                "active directory",
                "office 365",
                "networking",
                "dns",
                "dhcp",
                "vpn",
                "incident management",
            },
            "minimum_score": 95.0,
        },
        {
            "name": "project_manager",
            "cv_title": "Chef de projet Agile",
            "job_title": "Chef de projet",
            "cv_text": """
            Salma Chef de projet
            Pilotage Agile Scrum et Kanban avec Jira et Confluence.
            Gestion des risques, stakeholder management, requirements gathering, change management,
            roadmap, planning et budget tracking.
            """,
            "job_text": """
            Chef de projet / Project Manager
            Requis : Agile, Scrum, Jira, gestion des risques, stakeholder management,
            recueil des besoins, conduite du changement, roadmap et planning.
            """,
            "expected_cv_skills": {
                "agile",
                "scrum",
                "kanban",
                "jira",
                "confluence",
                "risk management",
                "stakeholder management",
                "requirements gathering",
                "change management",
                "roadmap",
                "planning",
                "budget tracking",
            },
            "expected_job_skills": {
                "agile",
                "scrum",
                "jira",
                "risk management",
                "stakeholder management",
                "requirements gathering",
                "change management",
                "roadmap",
                "planning",
            },
            "minimum_score": 95.0,
        },
    ],
)
def test_non_data_profiles_detect_representative_skills_and_score_coherently(case: dict) -> None:
    cv_document = DocumentText(
        filename=f"{case['name']}_cv.txt",
        text=case["cv_text"],
        char_count=len(case["cv_text"]),
    )
    cv_payload = {
        "candidate_name": f"Candidat {case['name']}",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [{"job_title": case["cv_title"], "missions": [case["cv_text"]]}],
        "education": [],
        "languages": [],
    }
    job_document = DocumentText(
        filename=f"{case['name']}_job.txt",
        text=case["job_text"],
        char_count=len(case["job_text"]),
    )
    job_payload = {
        "job_title": case["job_title"],
        "required_skills": {"mandatory": [], "preferred": [], "soft": []},
    }

    cv = CVExtractor(StaticLLM(cv_payload)).extract(cv_document)
    job = JobExtractor(StaticLLM(job_payload)).extract(job_document)
    score = ScoringEngine().score_candidate(cv_document.filename, cv, job, [])

    detected_cv_skills = set(cv.skills.technical + cv.skills.tools)
    assert case["expected_cv_skills"].issubset(detected_cv_skills)
    assert case["expected_job_skills"].issubset(set(job.required_skills.mandatory))
    assert score.final_score >= case["minimum_score"]


def test_non_data_profile_scoring_is_stable_across_repeated_runs() -> None:
    text = """
    Developpeur Backend
    Java, Spring Boot, API REST, Docker, PostgreSQL et Git.
    """
    cv_payload = {
        "candidate_name": "Candidat Stable",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [{"job_title": "Developpeur Backend", "missions": [text]}],
    }
    job_payload = {
        "job_title": "Developpeur Backend",
        "required_skills": {"mandatory": [], "preferred": [], "soft": []},
    }

    results = []
    for _ in range(3):
        cv_document = DocumentText(filename="stable_cv.txt", text=text, char_count=len(text))
        job_document = DocumentText(filename="stable_job.txt", text=text, char_count=len(text))
        cv = CVExtractor(StaticLLM(cv_payload)).extract(cv_document)
        job = JobExtractor(StaticLLM(job_payload)).extract(job_document)
        score = ScoringEngine().score_candidate(cv_document.filename, cv, job, [])
        results.append(
            {
                "cv_skills": cv.skills.technical + cv.skills.tools,
                "job_mandatory": job.required_skills.mandatory,
                "score": score.final_score,
                "matched": score.category_scores[0].matched,
                "missing": score.category_scores[0].missing,
            }
        )

    assert results[0] == results[1] == results[2]


def test_job_extractor_accepts_model_lists_returned_as_objects() -> None:
    text = """
    Data analyst packaging tool (SPM)
    Tools : Power BI, Excel et eventually Foundry
    Data available in datalake Snowflake + Azure
    lead data workstream with ITMS to clarify business needs
    Creation of KPI / dashbord in Power BI or Foundry
    fluent French & English
    autonomy and leadership
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": {"name": "Data analyst packaging tool (SPM)"},
        "required_skills": {
            "mandatory": [{"name": "Power BI"}, {"name": "Excel"}, {"name": "Snowflake"}],
            "preferred": [{"name": "Foundry"}],
            "soft": [{"name": "Autonomy"}, {"name": "Leadership"}],
        },
        "experience_requirements": {
            "minimum_months": "12 months",
            "preferred_job_titles": [{"title": "Data analyst"}],
            "required_domains": [{"domain": "Supply chain"}],
        },
        "education_requirements": {
            "minimum_level": {"level": "master"},
            "accepted_fields": [{"field": "data"}],
        },
        "language_requirements": [{"name": "French"}, {"name": "English"}],
        "certifications": [{"name": "PL-300"}],
        "responsibilities": [{"name": "Create and enhance dashboards"}],
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.required_skills.mandatory == ["power bi", "excel", "snowflake", "dashboard", "kpi", "azure"]
    assert job.required_skills.preferred == ["foundry", "business needs", "spm", "itms"]
    assert job.required_skills.soft == ["autonomy", "leadership"]
    assert job.experience_requirements.minimum_months == 12
    assert job.experience_requirements.preferred_job_titles == ["Data analyst"]
    assert job.experience_requirements.required_domains == []
    assert job.education_requirements.minimum_level == "master"
    assert job.education_requirements.accepted_fields == ["data"]
    assert [language.language for language in job.language_requirements] == ["francais", "anglais"]
    assert job.certifications == ["PL-300"]


def test_job_extractor_drops_implicit_required_domains_from_llm() -> None:
    text = """
    Data analyst packaging tool (SPM)
    Workstream BI/Data pour Supply Chain et transport.
    Tools : Power BI, Excel, Snowflake et Azure.
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Data Analyst",
        "experience_requirements": {
            "required_domains": ["Supply chain", "Transport"],
        },
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.experience_requirements.required_domains == []


def test_job_extractor_keeps_explicit_required_domains_from_text() -> None:
    text = """
    Data analyst packaging tool (SPM)
    Required domain: Supply Chain.
    Tools : Power BI, Excel, Snowflake et Azure.
    """
    document = DocumentText(filename="fiche_de_poste.txt", text=text, char_count=len(text))
    llm_payload = {
        "job_title": "Data Analyst",
        "experience_requirements": {
            "required_domains": ["Supply Chain", "Transport"],
        },
    }

    job = JobExtractor(StaticLLM(llm_payload)).extract(document)

    assert job.experience_requirements.required_domains == ["supply chain"]


def test_cv_extractor_does_not_turn_education_or_mission_fragments_into_experiences() -> None:
    text = """
    Soufyane Candidat
    Formation
    Ingenieur d'Etat en Data et Logiciels 2021 - 2024
    Master Informatique 2019 - 2021
    Experience
    Developpeur Full Stack janvier 2023 - decembre 2024
    Reporting SQL et visualisation Azure pour des tableaux de suivi.
    """
    document = DocumentText(filename="soufyane.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Soufyane",
        "experiences": [
            {"job_title": "Master Informatique", "start_date": "2020", "end_date": "2022"},
            {"job_title": "Python et NodeJS pour un backend robuste", "start_date": "2022", "end_date": "2023"},
            {
                "job_title": "Developpeur Full Stack",
                "start_date": "janvier 2023",
                "end_date": "decembre 2024",
                "missions": ["Reporting SQL et visualisation Azure pour des tableaux de suivi."],
            },
        ],
        "education": [
            {"degree": "Ingenieur d'Etat en Data et Logiciels", "start_year": 2021, "end_year": 2024},
            {"degree": "Master Informatique", "start_year": 2019, "end_year": 2021},
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.job_title for experience in cv.experiences] == ["Developpeur Full Stack"]
    assert [education.degree for education in cv.education] == [
        "Ingenieur d'Etat en Data et Logiciels",
        "Master Informatique",
    ]
    assert all("master" not in (experience.job_title or "").lower() for experience in cv.experiences)


def test_cv_extractor_filters_noisy_llm_experience_titles() -> None:
    document = DocumentText(filename="zakariaa.txt", text="CV Zakariaa", char_count=11)
    llm_payload = {
        "candidate_name": "Zakariaa",
        "experiences": [
            {"job_title": "Master Informatique", "start_date": "2020", "end_date": "2022"},
            {"job_title": "Python et NodeJS pour un backend robuste", "start_date": "2022", "end_date": "2023"},
            {"job_title": "Developpeur Full Stack", "start_date": "janvier 2023", "end_date": "decembre 2024"},
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.job_title for experience in cv.experiences] == ["Developpeur Full Stack"]


def test_cv_extractor_accepts_model_missions_returned_as_objects() -> None:
    document = DocumentText(filename="soufyane.txt", text="CV Soufyane", char_count=11)
    llm_payload = {
        "candidate_name": "Soufyane",
        "skills": {"technical": [{"skill": "Azure"}]},
        "experiences": [
            {
                "job_title": "Developpeur Full Stack",
                "company": "Experteye",
                "missions": [
                    {"mission": "Pilotage du developpement de la plateforme SaaS RentalEye"},
                    {"description": "Visualisation de donnees et reporting interne"},
                ],
                "skills_used": [{"skill": "Azure"}, {"technology": "SQL"}],
            }
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.skills.technical == ["azure"]
    assert cv.experiences[0].missions == [
        "Pilotage du developpement de la plateforme SaaS RentalEye",
        "Visualisation de donnees et reporting interne",
    ]
    assert cv.experiences[0].skills_used == ["azure", "sql"]


def test_cv_extractor_keeps_explicit_tools_present_only_in_raw_text() -> None:
    text = """
    OAKKI Sounia
    Data Analyst
    Analyse et visualisation des donnees avec Power BI.
    Outils : Power BI, DAX, Power Automate, Power Apps, SharePoint,
    Microsoft Excel, Python, Pandas, PostgreSQL, SQL.
    """
    document = DocumentText(filename="oakki.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "OAKKI Sounia",
        "skills": {"technical": [], "tools": ["Power BI"], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert "power bi" in cv.skills.tools
    assert "excel" in cv.skills.tools
    assert "dax" in cv.skills.tools
    assert "power automate" in cv.skills.tools
    assert "power apps" in cv.skills.tools
    assert "sharepoint" in cv.skills.tools
    assert "python" in cv.skills.technical
    assert "pandas" in cv.skills.technical
    assert "postgresql" in cv.skills.technical
    assert "sql" in cv.skills.technical
    assert "dashboard" not in cv.skills.tools
    assert "kpi" not in cv.skills.tools


def test_cv_extractor_does_not_count_azure_ad_as_data_azure_skill() -> None:
    text = """
    Support IT
    Outils: Office 365, Exchange, Azure AD, VDI, ServiceNow, Microsoft Excel.
    """
    document = DocumentText(filename="support.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Support IT",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert "azure" not in cv.skills.tools
    assert "azure ad" in cv.skills.tools
    assert "excel" in cv.skills.tools


def test_cv_job_skill_enrichment_uses_raw_text_for_requested_skills_only() -> None:
    text = """
    Projet technique
    Mise en place d'une API robuste avec Fast API et documentation OpenAPI.
    """
    document = DocumentText(filename="candidate.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }
    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)
    job = StructuredJobDescription(
        required_skills=RequiredSkills(mandatory=["FastAPI", "Snowflake"])
    )

    enrich_cv_with_job_skill_evidence(cv, document.text, job)

    assert "fastapi" in cv.skills.technical
    assert "snowflake" not in cv.skills.technical


def test_cv_job_skill_enrichment_removes_unverified_requested_llm_skills() -> None:
    raw_text = """
    Analyse KPI avancee avec Microsoft Excel.
    """
    cv = StructuredCV(
        candidate_name="Candidate",
        skills=SkillSet(technical=["Power BI", "Excel"], tools=[]),
        experiences=[Experience(skills_used=["Power BI", "KPI"])],
    )
    job = StructuredJobDescription(
        required_skills=RequiredSkills(mandatory=["Power BI", "Excel", "KPI"])
    )

    enrich_cv_with_job_skill_evidence(cv, raw_text, job)

    candidate_skills = cv.skills.technical + cv.skills.tools + cv.experiences[0].skills_used
    assert "power bi" not in candidate_skills
    assert "excel" in candidate_skills
    assert "kpi" in candidate_skills


def test_cv_extractor_does_not_count_internships_as_professional_experience() -> None:
    document = DocumentText(filename="candidate.txt", text="CV Candidate", char_count=12)
    llm_payload = {
        "candidate_name": "Candidate",
        "experiences": [
            {"job_title": "Stage Developpeur Data", "start_date": "janvier 2024", "end_date": "juin 2024"},
            {"job_title": "Developpeur Data", "start_date": "juillet 2024", "end_date": "decembre 2024"},
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.job_title for experience in cv.experiences] == ["Developpeur Data"]


def test_cv_extractor_keeps_explicit_bilingual_soft_skills_from_raw_text() -> None:
    text = """
    Qualites
    Autonomie, leadership, self-driven, communication.
    """
    document = DocumentText(filename="soft.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.skills.soft == ["autonomy", "leadership", "self driven"]


def test_cv_extractor_recovers_languages_from_raw_text_when_llm_omits_them() -> None:
    text = """
    Langues
    Arabe (Maternelle) - Anglais (Professionnel) - Francais (Courant)
    """
    document = DocumentText(filename="languages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [(language.language, language.normalized_level) for language in cv.languages] == [
        ("francais", "fluent"),
        ("anglais", "professional"),
        ("arabe", "native"),
    ]


def test_cv_extractor_accepts_language_level_returned_by_model() -> None:
    document = DocumentText(filename="languages.txt", text="Langues: Francais courant", char_count=25)
    llm_payload = {
        "candidate_name": "Candidate",
        "languages": [{"language": "French", "level": "courant"}],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.languages[0].language == "francais"
    assert cv.languages[0].normalized_level == "courant"


def test_cv_extractor_overrides_unknown_llm_language_level_with_raw_text_evidence() -> None:
    text = """
    LANGUES
    Arabe
    Langue maternelle
    anglais
    Capacite professionnelle complete
    Francais
    Capacite professionnelle complete
    """
    document = DocumentText(filename="vertical-languages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [
            {"language": "anglais", "normalized_level": "niveau non precise"},
            {"language": "francais", "normalized_level": "niveau non precise"},
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert {(language.language, language.normalized_level) for language in cv.languages} == {
        ("anglais", "professional"),
        ("francais", "professional"),
        ("arabe", "native"),
    }


def test_cv_extractor_accepts_education_years_returned_as_month_year_strings() -> None:
    document = DocumentText(filename="zakariaa.txt", text="CV Zakariaa", char_count=11)
    llm_payload = {
        "candidate_name": "Zakariaa",
        "education": [
            {
                "degree": "Master",
                "institution": "Faculte des sciences et technologies",
                "start_year": "September 2018",
                "end_year": "October 2020",
            },
            {
                "degree": "Licence",
                "institution": "Faculte des sciences et technologies",
                "start_year": "September 2017",
                "end_year": "June 2018",
            },
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [(education.start_year, education.end_year) for education in cv.education] == [
        (2018, 2020),
        (2017, 2018),
    ]


def test_cv_extractor_normalizes_companies_and_abbreviated_french_dates() -> None:
    text = """
    Zakariaa
    Experience
    Experteye Developpeur FullStack JavaScript Mar 2022 - Juil 2022
    BCP Developpeur Backend sept 2022 - dec 2022
    Formation
    Master Informatique 2020 - 2022
    Licence Informatique 2017 - 2020
    """
    document = DocumentText(filename="zakariaa.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Zakariaa",
        "experiences": [
            {
                "job_title": "Experteye Developpeur FullStack JavaScript",
                "company": None,
                "start_date": "Mar 2022",
                "end_date": "Juil 2022",
                "missions": ["Experteye Developpement de modules React et NodeJS."],
            },
            {
                "job_title": "BCP Developpeur Backend",
                "company": None,
                "start_date": "sept 2022",
                "end_date": "dec 2022",
                "missions": ["BCP API Python et NodeJS pour un backend robuste."],
            },
        ],
        "education": [
            {"degree": "Master Informatique", "start_year": 2020, "end_year": 2022},
            {"degree": "Licence Informatique", "start_year": 2017, "end_year": 2020},
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.company for experience in cv.experiences] == ["Experteye", "BCP"]
    assert [experience.duration_months for experience in cv.experiences] == [5, 4]
    assert [education.degree for education in cv.education] == ["Master Informatique", "Licence Informatique"]
    assert [(education.start_year, education.end_year) for education in cv.education] == [(2020, 2022), (2017, 2020)]


def test_cv_extractor_keeps_insea_engineering_education() -> None:
    text = """
    Soufyane
    Formation
    Ingenieur d'Etat en Data et Logiciels
    INSEA
    2019 - 2022
    """
    document = DocumentText(filename="soufyane.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Soufyane",
        "education": [
            {
                "degree": "Ingenieur d'Etat en Data et Logiciels",
                "institution": "INSEA",
                "start_year": 2019,
                "end_year": 2022,
            }
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.education
    assert cv.education[0].degree == "Ingenieur d'Etat en Data et Logiciels"
    assert cv.education[0].institution == "INSEA"
    assert cv.education[0].start_year == 2019
    assert cv.education[0].end_year == 2022
    assert len(cv.education) == 1


def test_cv_extractor_recovers_candidate_name_from_visible_raw_text() -> None:
    text = """
    I N G E N I E U R   L O G I C I E L
    SILLAHI Chaimaa
    Casablanca, Maroc
    EXPERIENCE PROFESSIONNELLE
    Cheffe de projet logiciel
    """
    document = DocumentText(filename="cv7.pdf", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "cv_cv7.pdf",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.candidate_name == "SILLAHI Chaimaa"

# Role dans le projet:
# Ce fichier contient les tests unitaires pour extraction. Il protege le comportement existant pendant les refactors sans appeler les services externes.
