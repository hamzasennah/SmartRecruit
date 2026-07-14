from app.schemas.matching import CandidateMatch, CategoryScore, Evidence
from app.services.matching.education_matcher import match_education
from app.services.matching.experience_matcher import match_experience
from app.services.matching.language_matcher import match_languages
from app.services.matching.responsibility_matcher import match_responsibilities
from app.services.matching.skill_matcher import match_skills, match_soft_skills
from app.services.scoring.explanation_builder import build_strengths, build_weaknesses
from app.services.scoring.weights import load_scoring_weights


class ScoringEngine:
    def score_candidate(self, filename, cv, job, retrieved_evidence=None) -> CandidateMatch:
        weights = load_scoring_weights()
        results = {
            "technical_skills": match_skills(cv, job),
            "experience": match_experience(cv, job),
            "responsibilities": match_responsibilities(cv, job, retrieved_evidence),
            "education": match_education(cv, job),
            "languages": match_languages(cv, job),
            "soft_skills": match_soft_skills(cv, job),
        }
        applicable_results = {
            name: result
            for name, result in results.items()
            if result.get("applicable", True)
        }
        rows = [
            _category(name, result, weights, applicable_results)
            for name, result in applicable_results.items()
        ]
        evidence = [
            Evidence(
                source=str(item.get("metadata", {}).get("section", "retrieval")),
                text=str(item.get("text", "")),
                score=float(item.get("rerank_score", item.get("score", 0.0))),
                metadata=item.get("metadata", {}),
            )
            for item in (retrieved_evidence or [])[:8]
        ]
        return CandidateMatch(
            candidate_name=cv.candidate_name or filename,
            filename=filename,
            final_score=round(sum(row.weighted_score for row in rows), 2),
            category_scores=rows,
            strengths=build_strengths(rows),
            weaknesses=build_weaknesses(rows),
            evidence=evidence,
        )


def _category(name, result, weights, applicable_results) -> CategoryScore:
    active_weight_sum = sum(weights.get(category, 0.0) for category in applicable_results) or 1.0
    weight = weights.get(name, 0.0) / active_weight_sum
    score = float(result["score"])
    details = dict(result.get("details", {}))
    details["base_weight"] = round(weights.get(name, 0.0), 4)
    details["redistributed_weight"] = round(weight, 4)
    return CategoryScore(
        name=name,
        score=round(score, 2),
        weight=round(weight, 4),
        weighted_score=round(score * weight, 2),
        matched=result.get("matched", []),
        missing=result.get("missing", []),
        details=details,
    )
