from app.schemas.cv import Experience, SkillSet, StructuredCV
from app.schemas.job import ExperienceRequirement, RequiredSkills, StructuredJobDescription
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.scoring.scoring_engine import ScoringEngine


def test_scoring_engine_returns_explainable_match() -> None:
    cv = StructuredCV(
        candidate_name="Candidat Data",
        skills=SkillSet(technical=["python", "sql", "power bi"]),
        experiences=enrich_experience_durations([Experience(job_title="Data Analyst", start_date="01/2022", end_date="12/2024", skills_used=["python", "sql"])]),
    )
    job = StructuredJobDescription(
        job_title="Data Analyst",
        required_skills=RequiredSkills(mandatory=["python", "sql"], preferred=["power bi"]),
        experience_requirements=ExperienceRequirement(minimum_months=24, preferred_job_titles=["data analyst"]),
    )
    match = ScoringEngine().score_candidate("cv.txt", cv, job, [])
    assert match.final_score > 70
    assert match.category_scores

