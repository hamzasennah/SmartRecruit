from datetime import date

from app.schemas.cv import StructuredCV
from app.schemas.job import StructuredJobDescription
from app.services.experience.duration_calculator import experience_to_period
from app.services.experience.overlap_manager import calculate_total_unique_months, parse_period_value
from app.services.experience.relevance_calculator import tag_relevance


def match_experience(cv: StructuredCV, job: StructuredJobDescription) -> dict:
    required = job.experience_requirements.minimum_months
    periods: list[tuple[date, date]] = []
    relevant: list[tuple[date, date]] = []
    explicit_total = explicit_relevant = 0
    for experience in tag_relevance(cv.experiences, job):
        period = experience_to_period(experience)
        if period:
            parsed = (parse_period_value(period.start_date), parse_period_value(period.end_date))
            periods.append(parsed)
            if experience.relevance_score >= 0.45:
                relevant.append(parsed)
        elif experience.duration_months:
            explicit_total += experience.duration_months
            if experience.relevance_score >= 0.45:
                explicit_relevant += experience.duration_months
    total_months = calculate_total_unique_months(periods) if periods else explicit_total
    relevant_months = calculate_total_unique_months(relevant) if relevant else explicit_relevant or total_months
    score = 100.0 if required <= 0 else round(min(relevant_months / required, 1.0) * 100, 2)
    return {"score": score, "matched": [f"{relevant_months} mois pertinents"], "missing": [] if score >= 100 else [f"{max(required - relevant_months, 0)} mois pertinents manquants"], "details": {"total_experience_months": total_months, "relevant_experience_months": relevant_months, "required_experience_months": required}}

