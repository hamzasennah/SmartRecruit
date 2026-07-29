from app.schemas.ranking import RankedCandidate

DISPLAY_SCORE_DECIMALS = 2


class RankingEngine:
    def rank(self, matches) -> list[RankedCandidate]:
        ordered = sorted(matches, key=_ranking_sort_key)
        # Ties are based on display-rounded scores so the rank shown in the UI
        # matches the precision recruiters actually see.
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


def _ranking_sort_key(item) -> tuple[float, str, str]:
    match = item[0]
    # Name and filename make ordering deterministic when final scores tie.
    return (
        -float(match.final_score),
        str(match.candidate_name or "").casefold(),
        str(match.filename or "").casefold(),
    )


def _score_groups(ordered_matches) -> list[list]:
    groups: list[list] = []
    for item in ordered_matches:
        if not groups:
            groups.append([item])
            continue
        group_score = _display_score(groups[-1][0])
        if group_score == _display_score(item):
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups


def _display_score(item) -> float:
    return round(float(item[0].final_score), DISPLAY_SCORE_DECIMALS)

# Role dans le projet:
# Ce fichier trie les candidats et gere les ex aequo. Il reste separe du scoring pour isoler la presentation du classement.
