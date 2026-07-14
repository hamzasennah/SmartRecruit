from app.schemas.ranking import RankedCandidate


class RankingEngine:
    def rank(self, matches) -> list[RankedCandidate]:
        ordered = sorted(matches, key=lambda item: item[0].final_score, reverse=True)
        score_counts: dict[float, int] = {}
        for match, _ in ordered:
            score_counts[round(match.final_score, 2)] = score_counts.get(round(match.final_score, 2), 0) + 1

        ranked: list[RankedCandidate] = []
        previous_score: float | None = None
        current_rank = 0
        for position, (match, cv) in enumerate(ordered, start=1):
            score = round(match.final_score, 2)
            if previous_score is None or score != previous_score:
                current_rank = position
                previous_score = score
            is_tied = score_counts[score] > 1
            ranked.append(
                RankedCandidate(
                    rank=current_rank,
                    rank_label=f"{current_rank} ex aequo" if is_tied else str(current_rank),
                    is_tied=is_tied,
                    candidate=match,
                    structured_cv=cv,
                )
            )
        return ranked
