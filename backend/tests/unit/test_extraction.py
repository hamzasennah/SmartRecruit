from app.schemas.document import DocumentText
from app.services.extraction.cv_extractor import CVExtractor
from app.services.extraction.job_extractor import JobExtractor


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
    assert job.required_skills.preferred == ["foundry", "project management", "business needs"]
    assert job.experience_requirements.minimum_months == 12
    assert job.responsibilities == [
        "Creer et ameliorer les tableaux de bord et KPI.",
        "Piloter le workstream BI/Data.",
        "Clarifier les besoins metiers et assurer leur couverture.",
        "Garantir la disponibilite des donnees dans Snowflake/Azure.",
    ]


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
