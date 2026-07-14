from app.schemas.document import DocumentText
from app.services.extraction.cv_extractor import CVExtractor
from app.services.extraction.job_extractor import JobExtractor


class DisabledLLM:
    enabled = False


class NoisyLLM:
    enabled = True

    def generate_json(self, prompt: str) -> dict:
        return {
            "candidate_name": "Zakariaa",
            "experiences": [
                {
                    "job_title": "Master Informatique",
                    "start_date": "2020",
                    "end_date": "2022",
                },
                {
                    "job_title": "Python et NodeJS pour un backend robuste",
                    "start_date": "2022",
                    "end_date": "2023",
                },
                {
                    "job_title": "Developpeur Full Stack",
                    "start_date": "janvier 2023",
                    "end_date": "decembre 2024",
                },
            ],
        }


def test_job_extractor_keeps_data_analyst_requirements_from_realistic_job_sheet() -> None:
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

    job = JobExtractor(DisabledLLM()).extract(document)

    skills = set(job.required_skills.mandatory + job.required_skills.preferred)
    assert {
        "power bi",
        "excel",
        "dashboard",
        "kpi",
        "snowflake",
        "azure",
        "foundry",
        "project management",
        "business needs",
    }.issubset(skills)
    assert job.experience_requirements.minimum_months == 12
    assert not any(item.lower().startswith("by it solution") for item in job.responsibilities)
    assert any("lead data workstream" in item.lower() for item in job.responsibilities)


def test_cv_extractor_does_not_turn_education_or_mission_fragments_into_experiences() -> None:
    text = """
    Soufyane Candidat
    Formation
    Ingenieur d'Etat en Data et Logiciels 2021 - 2024
    Master Informatique 2019 - 2021
    Experience
    Developpeur Full Stack janvier 2023 - decembre 2024
    Reporting SQL et visualisation Azure pour des tableaux de suivi.
    que l'integration de pages utilisant des modeles IA 2022 - 2023
    Python et NodeJS pour un backend robuste 2021 - 2022
    """
    document = DocumentText(
        filename="soufyane.txt",
        text=text,
        char_count=len(text),
        sections={
            "education": "Ingenieur d'Etat en Data et Logiciels 2021 - 2024 Master Informatique 2019 - 2021",
            "experience": (
                "Developpeur Full Stack janvier 2023 - decembre 2024\n"
                "Reporting SQL et visualisation Azure pour des tableaux de suivi.\n"
                "que l'integration de pages utilisant des modeles IA 2022 - 2023\n"
                "Python et NodeJS pour un backend robuste 2021 - 2022"
            ),
        },
    )

    cv = CVExtractor(DisabledLLM()).extract(document)

    assert [experience.job_title for experience in cv.experiences] == ["Developpeur Full Stack"]
    assert all("master" not in (experience.job_title or "").lower() for experience in cv.experiences)
    assert all("ingenieur d'etat" not in (experience.job_title or "").lower() for experience in cv.experiences)


def test_cv_extractor_filters_noisy_llm_experience_titles() -> None:
    document = DocumentText(filename="zakariaa.txt", text="CV Zakariaa", char_count=11)

    cv = CVExtractor(NoisyLLM()).extract(document)

    assert [experience.job_title for experience in cv.experiences] == ["Developpeur Full Stack"]
