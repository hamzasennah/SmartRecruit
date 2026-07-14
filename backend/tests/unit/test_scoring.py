from app.schemas.cv import Experience, SkillSet, StructuredCV
from app.schemas.job import ExperienceRequirement, RequiredSkills, StructuredJobDescription
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.matching.experience_matcher import match_experience
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


def test_absent_criteria_are_ignored_and_weights_are_redistributed() -> None:
    cv = StructuredCV(
        candidate_name="Candidat Python",
        skills=SkillSet(technical=["python"]),
    )
    job = StructuredJobDescription(
        job_title="Data Analyst",
        required_skills=RequiredSkills(mandatory=["python", "sql"]),
    )

    match = ScoringEngine().score_candidate("cv.txt", cv, job, [])

    assert [category.name for category in match.category_scores] == ["technical_skills"]
    assert match.category_scores[0].weight == 1.0
    assert match.category_scores[0].score == 60.0
    assert match.final_score == 60.0


def test_irrelevant_experience_is_not_counted_as_relevant_months() -> None:
    cv = StructuredCV(
        candidate_name="Candidat JavaScript",
        skills=SkillSet(technical=["javascript", "react"]),
        experiences=enrich_experience_durations(
            [
                Experience(
                    job_title="Developpeur JavaScript",
                    start_date="janvier 2020",
                    end_date="decembre 2023",
                    missions=["Developpement d'interfaces web React et support front-end."],
                    skills_used=["javascript", "react"],
                )
            ]
        ),
    )
    job = StructuredJobDescription(
        job_title="Data Analyst",
        required_skills=RequiredSkills(mandatory=["power bi", "excel", "dashboard"]),
        experience_requirements=ExperienceRequirement(
            minimum_months=24,
            preferred_job_titles=["data analyst"],
        ),
        responsibilities=["Construire des dashboards et suivre les KPI metier."],
    )

    result = match_experience(cv, job)

    assert result["applicable"] is True
    assert result["score"] == 0.0
    assert result["details"]["total_experience_months"] == 48
    assert result["details"]["relevant_experience_months"] == 0
    assert result["missing"] == ["24 mois pertinents manquants"]
