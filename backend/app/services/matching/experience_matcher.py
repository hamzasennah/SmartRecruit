from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.experience.duration_calculator import calculate_cumulative_experience


def match_experience(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    required = job.experience_requirements.minimum_months
    calculated_totals = calculate_cumulative_experience(cv.experiences, cv.declared_total_experience)
    totals = cv.experience_totals if _has_experience_audit(cv) else calculated_totals
    details = _experience_details(totals, required)
    if required <= 0:
        # "applicable=False" protects candidates from a zero score when the job
        # description did not provide a duration requirement.
        return {
            "applicable": False,
            "score": 0.0,
            "matched": [],
            "missing": [],
            "details": details
            | {"reason": "Aucune duree minimale d'experience n'a ete detectee dans la fiche de poste."},
    }
    total_months = totals.total_months
    display_total_months = totals.calculated_total_months
    # The experience category validates the amount of reliable experience
    # extracted from the CV. Skill and responsibility categories already judge
    # whether that experience matches the target role.
    score = round(min(total_months / required, 1.0) * 100, 2)
    return {
        "applicable": True,
        "score": score,
        "matched": [f"{display_total_months} mois d'experience"] if display_total_months else [],
        "missing": [] if score >= 100 else [f"{max(required - total_months, 0)} mois d'experience manquants"],
        "details": details
        | {"experience_counting_policy": "Le minimum d'experience est compare au total fiable extrait du CV."},
    }


def _has_experience_audit(cv: StructuredCV) -> bool:
    totals = cv.experience_totals
    return bool(
        totals.calculation_source != "none"
        or totals.calculation_status != "not_available"
        or totals.entries
        or totals.declared_total_months is not None
    )


def _experience_details(totals, required: int) -> dict:
    return {
        "total_experience_months": totals.calculated_total_months,
        "total_experience_years": round(totals.calculated_total_months / 12, 2)
        if totals.calculated_total_months is not None
        else None,
        "dated_experience_months": totals.dated_months,
        "explicit_duration_months": totals.explicit_duration_months,
        "declared_total_experience_months": totals.declared_total_months,
        "experience_duration_trace": [entry.model_dump(mode="json") for entry in totals.entries],
        "experience_overlap_policy": totals.overlap_policy,
        "experience_calculation_source": totals.calculation_source,
        "experience_calculation_status": totals.calculation_status,
        "experience_calculation_failure_reason": totals.failure_reason,
        "required_experience_months": required,
    }

# Role dans le projet:
# Ce fichier matche la duree d'experience. Il compare le total fiable extrait du CV au minimum demande.
