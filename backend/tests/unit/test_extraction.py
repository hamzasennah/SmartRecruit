from datetime import date

import pytest
from app.schemas.cv import Experience, SkillSet, StructuredCV
from app.schemas.document import DocumentText
from app.schemas.job import RequiredSkills, StructuredJobDescription
from app.services.experience import duration_calculator
from app.services.extraction.cv_extractor import CVExtractor, enrich_cv_with_job_skill_evidence
from app.services.extraction.job_extractor import JobExtractor
from app.services.scoring.scoring_engine import ScoringEngine


class StaticLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.last_prompt: str | None = None
        self.last_output: dict | None = None

    def generate_json(self, prompt: str) -> dict:
        self.last_prompt = prompt
        self.last_output = self.payload
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
    assert [language.minimum_level for language in job.language_requirements] == ["fluent", "fluent"]


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
    assert [language.minimum_level for language in job.language_requirements] == ["fluent", "fluent"]


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


def test_cv_extractor_filters_education_records_misclassified_as_experiences() -> None:
    text = """
    Education
    2020 - 2023
    Licence Fondamentale en Genie de Telecommunication
    Faculte des Sciences et Techniques
    2019 - 2020
    Baccalaureat en sciences Mathematiques A
    Lycee Mohammed 5
    """
    document = DocumentText(filename="education-as-experience.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "experiences": [
            {
                "job_title": "Ingenieure en telecommunication",
                "company": "Faculte des Sciences et Techniques",
                "start_date": "2020",
                "end_date": "2023",
            },
            {
                "job_title": "Ingenieure en sciences Mathematiques",
                "company": "Lycee Mohammed 5",
                "start_date": "2019",
                "end_date": "2020",
            },
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.total_experience_months == 0
    assert all(not entry.counted_in_total for entry in cv.experience_totals.entries)


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


def test_cv_job_skill_enrichment_detects_plural_kpis_from_raw_text() -> None:
    raw_text = """
    Developed measures and KPIs using the DAX language.
    """
    cv = StructuredCV(
        candidate_name="Najlae Hmimina",
        skills=SkillSet(technical=[], tools=[]),
    )
    job = StructuredJobDescription(
        required_skills=RequiredSkills(mandatory=["KPI"])
    )

    enrich_cv_with_job_skill_evidence(cv, raw_text, job)

    assert "kpi" in cv.skills.technical + cv.skills.tools


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


def test_cv_extractor_keeps_explicit_stage_durations_in_total_audit_without_professional_scoring() -> None:
    text = """
    Experience
    Stage d'alternance(4mois) - 2025
    Stage (1mois) - 2024
    Stage de fin d'etude - Departement de diffusion (3mois) - 2023
    """
    document = DocumentText(filename="duration-only-stages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [
            {"job_title": "Stage d'alternance(4mois)", "start_date": "2025"},
            {"job_title": "Stage (1mois)", "start_date": "2024"},
            {"job_title": "Stage de fin d'etude - Departement de diffusion (3mois)", "start_date": "2023"},
        ],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.total_experience_months == 8
    assert cv.experience_totals.explicit_duration_months == 8
    assert cv.experience_totals.explicit_duration_count == 3


def test_cv_extractor_uses_directly_declared_total_experience_after_llm_extraction() -> None:
    text = """
    Candidate Data Analyst
    Profil: 4 ans d'experience en analyse de donnees.
    """
    document = DocumentText(filename="direct-total.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "declared_total_experience": "4 ans d'experience",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }
    llm = StaticLLM(llm_payload)

    cv = CVExtractor(llm).extract(document)

    assert llm.last_output == llm_payload
    assert "declared_total_experience" in (llm.last_prompt or "")
    assert cv.total_experience_months == 48
    assert cv.experience_totals.calculation_source == "declared_total_experience"


def test_cv_extractor_calculates_total_from_multiple_dated_llm_experiences() -> None:
    text = """
    Candidate Data Analyst
    Experience
    Data Analyst, 2020 a 2025
    Consultant BI, 2026 a 2028
    """
    document = DocumentText(filename="dated-ranges.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [
            {"job_title": "Data Analyst", "start_date": "De 2020 \u00e0 2025", "end_date": None},
            {"job_title": "Consultant BI", "start_date": "De 2026 \u00e0 2028", "end_date": None},
        ],
        "education": [],
        "languages": [],
    }
    llm = StaticLLM(llm_payload)

    cv = CVExtractor(llm).extract(document)

    assert llm.last_output == llm_payload
    assert [experience.duration_months for experience in cv.experiences] == [72, 36]
    assert cv.total_experience_months == 108
    assert cv.experience_totals.calculation_source == "itemized_experiences"


def test_cv_extractor_recovers_date_ranged_experiences_omitted_by_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 8, 2)

    monkeypatch.setattr(duration_calculator, "date", FrozenDate)
    text = """
    Candidate
    Experience
    Software Engineer
    04/2025 - present
    Data Scientist
    11/2021 - 02/2025
    BI Developer
    06/2024 - 11/2024
    Data Analyst
    02/2024 - 06/2024
    Data Engineer
    06/2023 - 08/2023
    Business Intelligence Analyst
    04/2022 - 06/2022
    """
    document = DocumentText(filename="six-ranges.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [
            {"job_title": "Software Engineer", "start_date": "04/2025", "end_date": "present"},
            {"job_title": "Data Scientist", "start_date": "11/2021", "end_date": "02/2025"},
        ],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.job_title for experience in cv.experiences] == [
        "Software Engineer",
        "Data Scientist",
        "BI Developer",
        "Data Analyst",
        "Data Engineer",
        "Business Intelligence Analyst",
    ]
    assert [experience.duration_months for experience in cv.experiences] == [17, 40, 6, 5, 3, 3]
    assert cv.experience_totals.period_count == 6
    assert len(cv.experience_totals.entries) == 6
    assert cv.total_experience_months == 57


def test_cv_extractor_recovers_pdf_layout_dates_separated_from_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    class FrozenDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 8, 2)

    monkeypatch.setattr(duration_calculator, "date", FrozenDate)
    text = """
    Professional Experience
    Software Engineer, Yorsil
    Developed front-end interface using React.js.
    Built and maintained back-end APIs with Node.js.
    04/2025 - present
    internship, inettech.io
    Development of an intelligent extraction system.
    11/2021 - 02/2025
    data scientist, Freelancer
    Developed deep learning models.
    06/2024 - 11/2024
    PFE master internship, Wehlp Group
    Participation in the development of an application.
    02/2024 - 06/2024
    Internship - Full Stack Development & Data Science, Creative Studio
    Web application for rentals.
    06/2023 - 08/2023
    Bachelor's PFE internship, TC Design
    Development of an e-commerce web application.
    04/2022 - 06/2022
    Education
    Master in Data Science
    2022 - 2024
    """
    document = DocumentText(filename="vertical-dates.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [
            {"job_title": "Software Engineer", "start_date": "04/2025"},
            {"job_title": "data scientist", "start_date": "06/2024", "end_date": "11/2024"},
        ],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experience_totals.period_count == 6
    assert len(cv.experience_totals.entries) == 6
    assert cv.total_experience_months == 57
    assert [experience.job_title for experience in cv.experiences] == ["Software Engineer", "data scientist"]
    assert cv.experiences[0].duration_months == 17


def test_cv_extractor_recovers_explicit_duration_entries_omitted_by_llm() -> None:
    text = """
    Experience
    Stage d'alternance(4mois) - 2025
    Stage (1mois) - 2024
    Stage de fin d'etude - Departement de diffusion (3mois) - 2023
    """
    document = DocumentText(filename="duration-only-stages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.total_experience_months == 8
    assert cv.experience_totals.explicit_duration_months == 8
    assert cv.experience_totals.explicit_duration_count == 3
    assert len(cv.experience_totals.entries) == 3


def test_cv_extractor_recovers_explicit_duration_entries_without_same_line_year() -> None:
    text = """
    Experience Professionnelle
    2025
    2024
    Stage (1 mois)
    sg2i consulting
    Stage de fin d'etude - Departement de diffusion (3mois)
    SOREAD 2M
    Stage d'alternance(4mois)
    sg2i Consulting
    2023
    """
    document = DocumentText(filename="duration-only-stages-layout.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.total_experience_months == 8
    assert cv.experience_totals.explicit_duration_months == 8
    assert cv.experience_totals.explicit_duration_count == 3


def test_cv_extractor_clears_inconsistent_year_range_when_explicit_duration_wins() -> None:
    text = """
    Experience Professionnelle
    Stage de fin d'etude - Departement de diffusion (3mois)
    SOREAD 2M
    2020 - 2023
    Licence Fondamentale
    """
    document = DocumentText(filename="explicit-duration-vs-education-years.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "experiences": [
            {
                "job_title": "Stage de fin d'etude - Departement de diffusion (3mois)",
                "company": "SOREAD 2M",
                "start_date": "2020",
                "end_date": "2023",
                "declared_duration": "3 mois",
            },
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.total_experience_months == 3
    assert cv.experience_totals.entries[0].start_date_raw is None
    assert cv.experience_totals.entries[0].end_date_raw is None
    assert cv.experience_totals.entries[0].duration_months == 3


def test_cv_extractor_keeps_undated_internships_in_total_audit_only() -> None:
    text = """
    Experience professionnelle
    Je souhaite mettre ces connaissances en pratique a travers un stage de fin d'etudes.
    Stage Developpeur Web, Amereo Consulting
    Realisation d'une application web.
    Stage PFE, Prefecture de Fes
    Gestion et realisation d'une application Desktop.
    """
    document = DocumentText(filename="undated-stages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "experiences": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.total_experience_months == 0
    assert [entry.job_title for entry in cv.experience_totals.entries] == [
        "Stage Developpeur Web, Amereo Consulting",
        "Stage PFE, Prefecture de Fes",
    ]
    assert all(not entry.counted_in_total for entry in cv.experience_totals.entries)


def test_cv_extractor_filters_project_section_misclassified_as_experience() -> None:
    text = """
    Candidate
    Experience
    REALISATION DES PROJETS
    Prediction ML avec Python et Django.
    Analyse du baccalaureat (1997-2024) avec Power BI.
    """
    document = DocumentText(filename="projects-as-experience.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [
            {
                "job_title": "REALISATION DES PROJETS",
                "missions": ["Analyse du baccalaureat (1997-2024) avec Power BI."],
            },
            {"job_title": "Analyste BI"},
        ],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [entry.job_title for entry in cv.experience_totals.entries] == ["Analyste BI"]
    assert [experience.job_title for experience in cv.experiences] == ["Analyste BI"]


def test_cv_extractor_excludes_dated_project_section_from_experience_total() -> None:
    text = """
    Candidate
    Experience Professionnelle
    Data Analyst
    06/2023 - 08/2023
    REALISATION DES PROJETS
    Data Analyst dashboard Power BI
    2020 - 2024
    """
    document = DocumentText(filename="dated-project-section.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [entry.job_title for entry in cv.experience_totals.entries] == ["Data Analyst"]
    assert cv.total_experience_months == 3
    assert cv.experience_totals.period_count == 1


def test_cv_extractor_excludes_explicit_project_duration_from_experience_total() -> None:
    text = """
    Candidate
    Experience Professionnelle
    Stage Data Analyst (2 mois)
    Entreprise Data
    Projets realises
    Projet BI Power BI (12 mois)
    Portfolio data (1 year)
    """
    document = DocumentText(filename="project-durations.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [entry.job_title for entry in cv.experience_totals.entries] == ["Stage Data Analyst"]
    assert cv.total_experience_months == 2
    assert cv.experience_totals.explicit_duration_months == 2


def test_cv_extractor_cleans_contact_prefix_from_recovered_stage_titles() -> None:
    text = """
    Candidate
    06 60 73 69 58 Experience Professionnelle
    candidate@example.com Stage d'alternance(4mois) 2025
    Linkedin : candidate-profile Stage (1 mois) 2024
    """
    document = DocumentText(filename="contact-prefix-stages.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [entry.job_title for entry in cv.experience_totals.entries] == ["Stage d'alternance", "Stage"]
    assert cv.total_experience_months == 5


def test_cv_extractor_keeps_stage_line_when_pdf_columns_place_it_after_project_heading() -> None:
    text = """
    Candidate
    Experience Professionnelle
    Stage (1 mois)
    Experience
    REALISATION DES PROJETS
    Analyse du baccalaureat (1997-2024)
    Stage d'alternance(4mois)
    """
    document = DocumentText(filename="stage-after-project-heading.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [entry.job_title for entry in cv.experience_totals.entries] == ["Stage", "Stage d'alternance"]
    assert cv.total_experience_months == 5


def test_cv_extractor_filters_llm_experience_when_evidence_is_only_in_english_project_section() -> None:
    text = """
    Candidate
    Projects
    Data Analyst dashboard
    2020 - 2024
    """
    document = DocumentText(filename="english-project-section.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "skills": {"technical": [], "tools": [], "soft": []},
        "experiences": [{"job_title": "Data Analyst", "start_date": "2020", "end_date": "2024"}],
        "education": [],
        "languages": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []
    assert cv.experience_totals.entries == []
    assert cv.total_experience_months == 0


def test_cv_extractor_filters_internship_marker_on_line_after_date() -> None:
    text = """
    Najlae Hmimina
    Professional Experience
    Groupe LabelVie
    February 2025 - July 2025
    Data Analyst / BI Developer - Final Year Internship
    Developed measures and KPIs using the DAX language.
    """
    document = DocumentText(filename="najlae.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Najlae Hmimina",
        "experiences": [
            {
                "job_title": "Data Analyst / BI Developer",
                "company": "Groupe LabelVie",
                "start_date": "February 2025",
                "end_date": "July 2025",
                "missions": ["Developed measures and KPIs using the DAX language."],
                "skills_used": ["Power BI", "KPI"],
            }
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experiences == []


def test_cv_extractor_counts_current_depuis_role_and_filters_stage_dates() -> None:
    text = """
    OAKKI Sounia
    Experiences professionnelles
    Data Analyst (Depuis 22/04/2024)
    Dieze Rabat - Maroc
    Analyse et visualisation avec Power BI, Microsoft Excel et PostgreSQL.
    Stage | Data Analyst (De 27/06/2022 a 26/12/2022)
    AXA Services Maroc Technopolis
    Creation de rapports Power BI et Excel.
    """
    document = DocumentText(filename="oakki.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "OAKKI Sounia",
        "experiences": [
            {
                "job_title": "Data Analyst (Depuis 22/04/2024)",
                "company": "Dieze Rabat",
                "start_date": "22/04/2024",
                "end_date": None,
                "missions": ["Analyse et visualisation avec Power BI, Microsoft Excel et PostgreSQL."],
                "skills_used": ["Power BI", "Excel", "PostgreSQL"],
            },
            {
                "job_title": "Data Analyst",
                "company": "AXA Services Maroc Technopolis",
                "start_date": "27/06/2022",
                "end_date": "26/12/2022",
                "missions": ["Creation de rapports Power BI et Excel."],
                "skills_used": ["Power BI", "Excel"],
            },
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [experience.company for experience in cv.experiences] == ["Dieze Rabat"]
    assert cv.experiences[0].job_title == "Data Analyst"
    assert cv.experiences[0].duration_months is not None
    assert cv.experiences[0].duration.end_precision == "present"


def test_cv_extractor_deduplicates_raw_stage_title_with_llm_title() -> None:
    text = """
    Experiences professionnelles
    Stage | Data Science and Business Analytics (De 01/04/2022 a 01/05/2022)
    The Sparks Foundation
    Outils: Power BI, Tableau, Python
    """
    document = DocumentText(filename="stage-duplicate.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "experiences": [
            {
                "job_title": "Data Science and Business Analytics",
                "company": "The Sparks Foundation",
                "start_date": "01/04/2022",
                "end_date": "01/05/2022",
            },
        ],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.experience_totals.period_count == 1
    assert len(cv.experience_totals.entries) == 1
    assert cv.total_experience_months == 2


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
    document = DocumentText(filename="languages.txt", text="Langues: Francais courant. Arabe: Langue natale", char_count=48)
    llm_payload = {
        "candidate_name": "Candidate",
        "languages": [{"language": "French", "level": "courant"}, {"language": "Arabic", "level": "Langue natale"}],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert cv.languages[0].language == "francais"
    assert cv.languages[0].normalized_level == "courant"
    assert cv.languages[1].language == "arabe"
    assert cv.languages[1].normalized_level == "native"


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


def test_cv_extractor_recovers_missing_education_and_nearby_years() -> None:
    text = """
    Education
    2023 - En cours
    CYCLE D'INGENIERIE
    Universite Mundiapolis
    Baccalaureat en sciences Mathematiques A
    2019 - 2020
    Baccalaureat
    Lycee Mohammed 5
    2020 - 2023
    Licence Fondamentale en Genie de Telecommunication
    Faculte des Sciences et Techniques
    FORMATIONS
    2019 - 2021
    Master Specialise Big Data & Cloud Computing
    Universite Ibn Tofail
    2019
    Baccalaureate, high school
    Experience
    PFE master internship
    02/2024 - 06/2024
    Projets
    Analyse du baccalaureat (1997-2024) : etude exploratoire Power BI.
    """
    document = DocumentText(filename="education-layout.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "education": [
            {"degree": "Licence Fondamentale en Genie de Telecommunication"},
            {"degree": "Master Specialise Big Data & Cloud Computing"},
            {"degree": "Baccalaureat en sciences Mathematiques A", "start_year": 2023, "end_year": 2020},
            {"degree": "Baccalaureat"},
            {"degree": "Baccalaureate", "start_year": 2019},
        ],
        "experiences": [],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    by_degree = {education.degree: education for education in cv.education}
    assert by_degree["Licence Fondamentale en Genie de Telecommunication"].start_year == 2020
    assert by_degree["Licence Fondamentale en Genie de Telecommunication"].end_year == 2023
    assert by_degree["Master Specialise Big Data & Cloud Computing"].start_year == 2019
    assert by_degree["Master Specialise Big Data & Cloud Computing"].end_year == 2021
    assert by_degree["Baccalaureat en sciences Mathematiques A"].start_year == 2019
    assert by_degree["Baccalaureat en sciences Mathematiques A"].end_year == 2020
    assert "Baccalaureat" not in by_degree
    baccalaureate = next(education for education in cv.education if education.degree.startswith("Baccalaureate"))
    assert baccalaureate.end_year == 2019
    assert by_degree["CYCLE D'INGENIERIE"].start_year == 2023
    assert by_degree["CYCLE D'INGENIERIE"].end_year is None
    assert "PFE master internship" not in by_degree
    assert "Analyse du baccalaureat (1997-2024) : etude exploratoire Power BI" not in by_degree


def test_cv_extractor_replaces_generic_education_degree_with_raw_source_title() -> None:
    text = """
    Diplomes et formation
    Master 2 en Ingenierie des systemes d'informations (Bac+5) Ecole
    Superieure d'Ingenierie En Sciences Appliquees
    Licence en Ingenierie Logicielle (Bac+3) Ecole Superieure d'Ingenierie En
    Sciences Appliquees
    """
    document = DocumentText(filename="generic-education.txt", text=text, char_count=len(text))
    llm_payload = {
        "candidate_name": "Candidate",
        "education": [{"degree": "Master 2"}, {"degree": "Licence"}],
    }

    cv = CVExtractor(StaticLLM(llm_payload)).extract(document)

    assert [education.degree for education in cv.education] == [
        "Master 2 en Ingenierie des systemes d'informations (Bac+5)",
        "Licence en Ingenierie Logicielle (Bac+3)",
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
