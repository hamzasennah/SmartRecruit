from app.schemas.document import DocumentText
from app.services.extraction.job_extractor import JobExtractor


class DisabledLLM:
    enabled = False


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
