from app.schemas.ranking import RankedCandidate


TIE_SCORE_TOLERANCE = 0.5


class RankingEngine:
    def rank(self, matches) -> list[RankedCandidate]:
        ordered = sorted(matches, key=lambda item: item[0].final_score, reverse=True)
        groups = _score_groups(ordered)

        ranked: list[RankedCandidate] = []
        position = 1
        for group in groups:
            current_rank = position
            is_tied = len(group) > 1
            for match, cv in group:
                ranked.append(
                    RankedCandidate(
                        rank=current_rank,
                        rank_label=f"{current_rank} ex æquo" if is_tied else str(current_rank),
                        is_tied=is_tied,
                        candidate=match,
                        structured_cv=cv,
                    )
                )
            position += len(group)
        return ranked


def _score_groups(ordered_matches) -> list[list]:
    groups: list[list] = []
    for item in ordered_matches:
        score = float(item[0].final_score)
        if not groups:
            groups.append([item])
            continue
        group_score = float(groups[-1][0][0].final_score)
        if abs(group_score - score) <= TIE_SCORE_TOLERANCE:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups
