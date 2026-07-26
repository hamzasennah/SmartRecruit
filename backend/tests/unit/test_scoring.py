from app.schemas.cv import Education, Experience, Language, SkillSet, StructuredCV
from app.schemas.job import ExperienceRequirement, LanguageRequirement, RequiredSkills, StructuredJobDescription
from app.services.experience.duration_calculator import enrich_experience_durations
from app.services.matching.experience_matcher import match_experience
from app.services.matching.language_matcher import match_languages
from app.services.matching.responsibility_matcher import match_responsibilities
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
    assert match.category_scores[0].score == 50.0
    assert match.final_score == 50.0
    assert match.category_scores[0].details["missing_mandatory"] == ["sql"]
    assert match.category_scores[0].details["missing_preferred"] == []


def test_skill_missing_lists_keep_mandatory_and_preferred_separated() -> None:
    cv = StructuredCV(
        candidate_name="Candidat Azure",
        skills=SkillSet(technical=["azure"]),
    )
    job = StructuredJobDescription(
        required_skills=RequiredSkills(
            mandatory=["power bi", "excel", "azure"],
            preferred=["foundry", "spm"],
        ),
    )

    match = ScoringEngine().score_candidate("cv.txt", cv, job, [])
    technical = match.category_scores[0]

    assert technical.missing == ["power bi", "excel"]
    assert technical.details["missing_mandatory"] == ["power bi", "excel"]
    assert technical.details["missing_preferred"] == ["foundry", "spm"]
    assert technical.details["mandatory_weight"] == 1.0
    assert technical.details["preferred_bonus_weight"] == 0.1


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


def test_responsibilities_require_specific_cv_evidence_not_single_keyword_overlap() -> None:
    cv = StructuredCV(
        candidate_name="Soufyane",
        skills=SkillSet(technical=["sql", "azure", "react"]),
        experiences=[
            Experience(
                job_title="Développeur Full Stack",
                missions=[
                    "Développement Full Stack avec React, TypeScript et NodeJS.",
                    "Mise en place de reporting SQL et visualisation de données sur Azure.",
                ],
                skills_used=["sql", "azure", "react"],
            )
        ],
    )
    job = StructuredJobDescription(
        job_title="Data Analyst",
        responsibilities=[
            "Tools : Power BI, Excel et Foundry",
            "Data available in datalake Snowflake + Azure",
            "BI/Data project management for SPM project",
        ],
    )

    result = match_responsibilities(
        cv,
        job,
        retrieved_evidence=[
            {
                "text": "Reporting SQL et visualisation de données sur Azure.",
                "score": 0.82,
            }
        ],
    )

    assert result["score"] == 0.0
    assert result["matched"] == []
    assert "Data available in datalake Snowflake + Azure" not in result["missing"]
    assert result["details"]["optional_responsibilities"][0]["responsibility"] == "Data available in datalake Snowflake + Azure"
    assert result["details"]["optional_responsibilities"][0]["status"] == "partial"


def test_responsibilities_give_partial_credit_for_reporting_and_visualisation() -> None:
    cv = StructuredCV(
        candidate_name="Soufyane",
        experiences=[
            Experience(
                job_title="Developpeur Full Stack",
                missions=[
                    "Reporting interne, automatisation des flux SQL et visualisation de donnees sur Azure.",
                    "Pilotage d'une plateforme traitant des millions de points de donnees.",
                ],
            )
        ],
    )
    job = StructuredJobDescription(
        responsibilities=[
            "Creer et ameliorer les tableaux de bord et KPI.",
            "Piloter le workstream BI/Data.",
            "Clarifier les besoins metiers et assurer leur couverture.",
            "Garantir la disponibilite des donnees dans Snowflake/Azure.",
        ],
    )

    result = match_responsibilities(cv, job, retrieved_evidence=[])

    assert 20.0 <= result["score"] < 70.0
    assert result["matched"] == []
    assert "Creer et ameliorer les tableaux de bord et KPI." in result["details"]["partial"]
    assert "Clarifier les besoins metiers et assurer leur couverture." not in result["missing"]
    assert result["details"]["optional_responsibilities"][0]["responsibility"] == (
        "Clarifier les besoins metiers et assurer leur couverture."
    )


def test_business_needs_responsibility_is_not_a_hard_penalty_when_unproven() -> None:
    cv = StructuredCV(
        candidate_name="Candidat",
        experiences=[
            Experience(
                job_title="Developpeur",
                missions=["Developpement d'une application web React."],
            )
        ],
    )
    job = StructuredJobDescription(
        responsibilities=["Clarifier les besoins metiers et assurer leur couverture."],
    )

    result = match_responsibilities(cv, job, retrieved_evidence=[])

    assert result["applicable"] is False
    assert result["missing"] == []
    assert result["details"]["optional_responsibilities"][0]["responsibility"] == (
        "Clarifier les besoins metiers et assurer leur couverture."
    )


def test_soft_skills_are_informative_and_do_not_penalize_scoring() -> None:
    cv = StructuredCV(
        candidate_name="Candidat Python",
        skills=SkillSet(technical=["python"]),
    )
    job = StructuredJobDescription(
        required_skills=RequiredSkills(
            mandatory=["python"],
            soft=["leadership", "autonomy", "self driven"],
        ),
    )

    match = ScoringEngine().score_candidate("cv.txt", cv, job, [])

    assert [category.name for category in match.category_scores] == ["technical_skills"]
    assert match.final_score == 100.0
    assert not any("Soft skills" in weakness for weakness in match.weaknesses)


def test_language_matching_uses_presence_and_normalized_level() -> None:
    cv = StructuredCV(
        languages=[
            Language(language="francais", normalized_level="courant"),
            Language(language="anglais", normalized_level="professional"),
        ],
    )
    job = StructuredJobDescription(
        language_requirements=[
            LanguageRequirement(language="French", minimum_level=None),
            LanguageRequirement(language="English", minimum_level="professional"),
        ],
    )

    result = match_languages(cv, job)

    assert result["matched"] == ["francais", "anglais"]
    assert result["missing"] == []
    assert result["score"] == 100.0


def test_language_matching_does_not_mark_present_language_missing_when_level_is_lower() -> None:
    cv = StructuredCV(
        languages=[
            Language(language="francais", normalized_level="professional"),
            Language(language="anglais", normalized_level="professional"),
        ],
    )
    job = StructuredJobDescription(
        language_requirements=[
            LanguageRequirement(language="French", minimum_level="fluent"),
            LanguageRequirement(language="English", minimum_level="fluent"),
        ],
    )

    result = match_languages(cv, job)

    assert result["matched"] == ["francais", "anglais"]
    assert result["missing"] == []
    assert result["score"] == 80.0
    assert result["details"]["below_required_level"] == [
        {"language": "francais", "candidate_rank": 4, "required_rank": 5},
        {"language": "anglais", "candidate_rank": 4, "required_rank": 5},
    ]


def test_language_matching_scores_native_as_full_credit() -> None:
    cv = StructuredCV(languages=[Language(language="English", normalized_level="native")])
    job = StructuredJobDescription(
        language_requirements=[LanguageRequirement(language="English", minimum_level="fluent")]
    )

    result = match_languages(cv, job)

    assert result["score"] == 100.0
    assert result["details"]["below_required_level"] == []


def test_experience_matching_adds_dated_periods_and_explicit_durations() -> None:
    cv = StructuredCV(
        skills=SkillSet(technical=["python"]),
        experiences=enrich_experience_durations(
            [
                Experience(
                    job_title="Data Analyst",
                    start_date="janvier 2021",
                    end_date="decembre 2021",
                    skills_used=["python"],
                ),
                Experience(
                    job_title="Data Analyst",
                    declared_duration="1 an",
                    skills_used=["python"],
                ),
            ]
        ),
    )
    job = StructuredJobDescription(
        required_skills=RequiredSkills(mandatory=["python"]),
        experience_requirements=ExperienceRequirement(
            minimum_months=24,
            preferred_job_titles=["data analyst"],
        ),
    )

    result = match_experience(cv, job)

    assert result["details"]["total_experience_months"] == 24
    assert result["details"]["relevant_experience_months"] == 24
    assert result["score"] == 100.0


def test_education_unknown_required_level_does_not_auto_match() -> None:
    from app.services.matching.education_matcher import match_education

    cv = StructuredCV(education=[Education(degree="Master Data", normalized_level="master", field="data")])
    job = StructuredJobDescription()
    job.education_requirements.minimum_level = "niveau mystere"

    result = match_education(cv, job)

    assert result["score"] == 0.0
    assert result["missing"] == ["niveau mystere"]
    assert result["details"]["unknown_required_level"] is True


def test_education_matching_uses_accepted_fields() -> None:
    from app.services.matching.education_matcher import match_education

    cv = StructuredCV(education=[Education(degree="Master Informatique", normalized_level="master", field="data")])
    job = StructuredJobDescription()
    job.education_requirements.minimum_level = "master"
    job.education_requirements.accepted_fields = ["data"]

    result = match_education(cv, job)

    assert result["score"] == 100.0
    assert result["matched"] == ["master", "data"]


def test_certification_and_domain_matching_is_not_automatic() -> None:
    from app.services.matching.certification_matcher import match_certifications_and_domains

    cv = StructuredCV(certifications=["PL-300"])
    job = StructuredJobDescription(certifications=["PL-300", "AZ-900"])
    job.experience_requirements.required_domains = ["supply chain"]

    result = match_certifications_and_domains(cv, job)

    assert result["score"] == 25.0
    assert result["matched"] == ["pl 300"]
    assert result["missing"] == ["az 900", "supply chain"]


def test_snowflake_azure_responsibility_rejects_generic_backend_database_evidence() -> None:
    cv = StructuredCV(
        candidate_name="Backend",
        experiences=[
            Experience(
                job_title="Developpeur Backend",
                missions=[
                    "Utilisation de Sequelize ORM pour l'interaction avec les bases de donnees MySQL et PostgreSQL dans le developpement back-end.",
                    "Deploiement avec Azure DevOps et pipelines CI/CD.",
                ],
            )
        ],
    )
    job = StructuredJobDescription(
        responsibilities=["Garantir la disponibilite des donnees dans Snowflake/Azure."],
    )

    result = match_responsibilities(cv, job, retrieved_evidence=[])

    assert result["applicable"] is False
    assert result["matched"] == []
    assert result["missing"] == []
    assert result["details"]["optional_responsibilities"][0]["status"] == "none"


def test_snowflake_azure_responsibility_accepts_only_data_platform_context() -> None:
    cv = StructuredCV(
        candidate_name="Data",
        experiences=[
            Experience(
                job_title="Data Analyst",
                missions=[
                    "Mise en place de pipelines ETL et flux de donnees sur Azure pour alimenter un data warehouse.",
                ],
            )
        ],
    )
    job = StructuredJobDescription(
        responsibilities=["Garantir la disponibilite des donnees dans Snowflake/Azure."],
    )

    result = match_responsibilities(cv, job, retrieved_evidence=[])

    assert result["applicable"] is False
    assert result["matched"] == []
    assert result["missing"] == []
    assert result["details"]["optional_responsibilities"][0]["status"] == "partial"


def test_snowflake_azure_responsibility_ignores_azure_devops_but_accepts_later_data_azure() -> None:
    cv = StructuredCV(
        candidate_name="Data",
        experiences=[
            Experience(
                job_title="Data Engineer",
                missions=[
                    "CI/CD avec Azure DevOps. Pipelines ETL de donnees sur Azure pour alimenter le data warehouse.",
                ],
            )
        ],
    )
    job = StructuredJobDescription(
        responsibilities=["Garantir la disponibilite des donnees dans Snowflake/Azure."],
    )

    result = match_responsibilities(cv, job, retrieved_evidence=[])

    assert result["applicable"] is False
    assert result["missing"] == []
    assert result["details"]["optional_responsibilities"][0]["status"] == "partial"


def test_responsibilities_ignore_language_sections_and_low_retrieval_scores() -> None:
    cv = StructuredCV(candidate_name="Candidat", skills=SkillSet(technical=[]))
    job = StructuredJobDescription(
        responsibilities=["Tools : Power BI, Excel et Foundry"],
    )

    result = match_responsibilities(
        cv,
        job,
        retrieved_evidence=[
            {
                "text": "Power BI Excel Foundry",
                "score": 0.95,
                "metadata": {"section": "languages"},
            },
            {
                "text": "Power BI Excel Foundry",
                "score": 0.19,
                "metadata": {"section": "experience"},
            },
        ],
    )

    assert result["score"] == 0.0
    assert result["matched"] == []


def test_scoring_engine_hides_irrelevant_or_weak_retrieved_evidence() -> None:
    cv = StructuredCV(candidate_name="Candidat", skills=SkillSet(technical=["power bi"]))
    job = StructuredJobDescription(required_skills=RequiredSkills(mandatory=["power bi"]))

    match = ScoringEngine().score_candidate(
        "cv.txt",
        cv,
        job,
        retrieved_evidence=[
            {
                "text": "Langues: francais anglais arabe",
                "score": 0.99,
                "metadata": {"section": "languages"},
            },
            {
                "text": "Power BI dashboard reporting.",
                "score": 0.19,
                "metadata": {"section": "experience"},
            },
            {
                "text": "Power BI dashboard reporting.",
                "score": 0.31,
                "metadata": {"section": "experience"},
            },
        ],
    )

    assert [evidence.source for evidence in match.evidence] == ["experience"]
    assert match.evidence[0].score == 0.31


def test_responsibility_score_uses_stable_document_sections_over_rag_topk() -> None:
    cv = StructuredCV(candidate_name="Candidat")
    job = StructuredJobDescription(
        responsibilities=["Piloter le workstream BI/Data."],
    )
    sections = {
        "experience": "Pilotage du workstream BI/Data avec coordination projet, reporting, dashboard et KPI data.",
    }
    weak_rag = [
        {
            "text": "Power BI seulement.",
            "score": 0.95,
            "metadata": {"section": "experience"},
        }
    ]
    strong_rag = [
        {
            "text": "Pilotage du workstream BI/Data avec reporting dashboard KPI.",
            "score": 0.95,
            "metadata": {"section": "experience"},
        }
    ]

    weak_match = ScoringEngine().score_candidate("cv.txt", cv, job, weak_rag, sections)
    strong_match = ScoringEngine().score_candidate("cv.txt", cv, job, strong_rag, sections)

    assert weak_match.final_score == strong_match.final_score
    assert weak_match.category_scores[0].score == strong_match.category_scores[0].score
