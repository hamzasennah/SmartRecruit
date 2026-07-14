from app.schemas.ranking import RankedCandidate


class RankingEngine:
    def rank(self, matches) -> list[RankedCandidate]:
        ordered = sorted(matches, key=lambda item: item[0].final_score, reverse=True)
        return [RankedCandidate(rank=i, candidate=match, structured_cv=cv) for i, (match, cv) in enumerate(ordered, start=1)]
