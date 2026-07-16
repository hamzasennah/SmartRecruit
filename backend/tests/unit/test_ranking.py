from app.schemas.cv import StructuredCV
from app.schemas.matching import CandidateMatch
from app.services.ranking.ranking_engine import RankingEngine


def test_ranking_engine_marks_equal_scores_as_tied() -> None:
    first = CandidateMatch(candidate_name="Zakariaa", filename="z.pdf", final_score=9.33, category_scores=[])
    second = CandidateMatch(candidate_name="Soufyane", filename="s.pdf", final_score=9.33, category_scores=[])
    third = CandidateMatch(candidate_name="Autre", filename="a.pdf", final_score=7.0, category_scores=[])

    ranking = RankingEngine().rank(
        [
            (first, StructuredCV(candidate_name="Zakariaa")),
            (second, StructuredCV(candidate_name="Soufyane")),
            (third, StructuredCV(candidate_name="Autre")),
        ]
    )

    assert [item.rank for item in ranking] == [1, 1, 3]
    assert [item.is_tied for item in ranking] == [True, True, False]
    assert [item.rank_label for item in ranking] == ["1 ex æquo", "1 ex æquo", "3"]


def test_ranking_engine_marks_tiny_score_differences_as_tied() -> None:
    first = CandidateMatch(candidate_name="Soufyane", filename="s.pdf", final_score=23.94, category_scores=[])
    second = CandidateMatch(candidate_name="Zakariaa", filename="z.pdf", final_score=23.90, category_scores=[])

    ranking = RankingEngine().rank(
        [
            (first, StructuredCV(candidate_name="Soufyane")),
            (second, StructuredCV(candidate_name="Zakariaa")),
        ]
    )

    assert [item.rank for item in ranking] == [1, 1]
    assert [item.is_tied for item in ranking] == [True, True]
    assert [item.rank_label for item in ranking] == ["1 ex æquo", "1 ex æquo"]
