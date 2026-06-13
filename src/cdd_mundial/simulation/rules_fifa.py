"""Pure FIFA World Cup 2026 group and best-third ranking rules.

Implements the official Article 13 tie-break cascade verified and pinned in
``03-01`` (D-03/D-04). The sequence is, in order:

1. Greater number of points in all group matches.
2. Goal difference in all group matches.
3. Goals scored in all group matches.
4. Greater number of points among the tied teams (head-to-head).
5. Goal difference in matches among the tied teams.
6. Goals scored in matches among the tied teams.
   -- if a subset is still level after 4-6, those criteria are reapplied to
      that subset alone before moving on.
7. Conduct score (fair-play points; less-negative ranks higher).
8. Successive editions of the FIFA ranking (lower rank number ranks higher).

There is no drawing of lots in the official 2026 regulation, so it is not
implemented. Every function is a pure, deterministic transform with no hidden
state, suitable for both batch simulation and direct unit testing.
"""

from __future__ import annotations

import pandas as pd

_TABLE_COLUMNS = [
    "team_id",
    "points",
    "goal_difference",
    "goals_for",
    "goals_against",
]


def calculate_group_table(matches: pd.DataFrame) -> pd.DataFrame:
    """Build a group standings table from played matches.

    ``matches`` must carry ``team_a``, ``team_b``, ``goals_a``, ``goals_b``.
    Returns one row per team with points, goal difference, goals for, and goals
    against, ordered by ``team_id`` for deterministic output. Ranking order is
    not applied here -- use :func:`rank_group`.
    """
    teams = sorted(set(matches["team_a"]) | set(matches["team_b"]))
    stats = {
        team: {"points": 0, "goals_for": 0, "goals_against": 0} for team in teams
    }
    for row in matches.itertuples(index=False):
        a, b = row.team_a, row.team_b
        ga, gb = int(row.goals_a), int(row.goals_b)
        stats[a]["goals_for"] += ga
        stats[a]["goals_against"] += gb
        stats[b]["goals_for"] += gb
        stats[b]["goals_against"] += ga
        if ga > gb:
            stats[a]["points"] += 3
        elif gb > ga:
            stats[b]["points"] += 3
        else:
            stats[a]["points"] += 1
            stats[b]["points"] += 1

    records = []
    for team in teams:
        s = stats[team]
        records.append(
            {
                "team_id": team,
                "points": s["points"],
                "goal_difference": s["goals_for"] - s["goals_against"],
                "goals_for": s["goals_for"],
                "goals_against": s["goals_against"],
            }
        )
    return pd.DataFrame.from_records(records, columns=_TABLE_COLUMNS)


def _overall_keys(table: pd.DataFrame) -> dict[str, tuple[int, int, int]]:
    return {
        row.team_id: (row.points, row.goal_difference, row.goals_for)
        for row in table.itertuples(index=False)
    }


def _head_to_head_keys(
    matches: pd.DataFrame, subset: list[str]
) -> dict[str, tuple[int, int, int]]:
    """Mini-table (points, GD, GF) computed only from matches among ``subset``."""
    members = set(subset)
    sub = matches[matches["team_a"].isin(members) & matches["team_b"].isin(members)]
    table = calculate_group_table(sub) if len(sub) else calculate_group_table(matches)
    keys = _overall_keys(table)
    # Teams in subset that never played each other still need a key.
    return {team: keys.get(team, (0, 0, 0)) for team in subset}


def _group_by_key(
    teams: list[str], key: dict[str, object]
) -> list[list[str]]:
    """Split ``teams`` into descending blocks sharing the same key value."""
    ordered = sorted(teams, key=lambda t: key[t], reverse=True)
    blocks: list[list[str]] = []
    for team in ordered:
        if blocks and key[blocks[-1][-1]] == key[team]:
            blocks[-1].append(team)
        else:
            blocks.append([team])
    return blocks


def _resolve_head_to_head(
    teams: list[str],
    matches: pd.DataFrame,
    conduct_scores: dict[str, float],
    fifa_ranking_editions: list[dict[str, float]],
) -> list[str]:
    """Apply head-to-head criteria to a tied block, reapplying on residual ties."""
    if len(teams) <= 1:
        return list(teams)

    h2h = _head_to_head_keys(matches, teams)
    blocks = _group_by_key(teams, h2h)

    if len(blocks) == 1:
        # Head-to-head did not separate anyone; fall through to later criteria.
        return _resolve_tail(teams, conduct_scores, fifa_ranking_editions)

    resolved: list[str] = []
    for block in blocks:
        if len(block) == len(teams):
            resolved.extend(
                _resolve_tail(block, conduct_scores, fifa_ranking_editions)
            )
        else:
            resolved.extend(
                _resolve_head_to_head(
                    block, matches, conduct_scores, fifa_ranking_editions
                )
            )
    return resolved


def _resolve_tail(
    teams: list[str],
    conduct_scores: dict[str, float],
    fifa_ranking_editions: list[dict[str, float]],
) -> list[str]:
    """Break a residual tie by conduct score, then successive FIFA editions."""
    if len(teams) <= 1:
        return list(teams)

    conduct_key = {team: conduct_scores[team] for team in teams}
    blocks = _group_by_key(teams, conduct_key)
    if len(blocks) > 1:
        resolved: list[str] = []
        for block in blocks:
            resolved.extend(
                _resolve_tail(block, conduct_scores, fifa_ranking_editions)
            )
        return resolved

    return _resolve_by_fifa_ranking(teams, fifa_ranking_editions)


def _resolve_by_fifa_ranking(
    teams: list[str],
    fifa_ranking_editions: list[dict[str, float]],
) -> list[str]:
    """Break a residual tie using successive FIFA-ranking editions (lower is better)."""
    if len(teams) <= 1:
        return list(teams)
    for edition in fifa_ranking_editions:
        # Lower rank number ranks higher, so negate for the descending splitter.
        edition_key = {team: -float(edition[team]) for team in teams}
        blocks = _group_by_key(teams, edition_key)
        if len(blocks) > 1:
            resolved: list[str] = []
            for block in blocks:
                resolved.extend(
                    _resolve_by_fifa_ranking(block, fifa_ranking_editions)
                )
            return resolved
    raise ValueError(
        "residual tie among "
        f"{sorted(teams)} cannot be resolved from the provided official data; "
        "drawing of lots is not permitted under the 2026 regulation"
    )


def rank_group(
    matches: pd.DataFrame,
    *,
    conduct_scores: dict[str, float],
    fifa_ranking_editions: list[dict[str, float]],
) -> list[str]:
    """Return group team IDs ordered first to last per the Article 13 cascade.

    ``conduct_scores`` maps each team to its fair-play score (<= 0; less-negative
    ranks higher). ``fifa_ranking_editions`` is an ordered list of edition maps
    (most recent first), each mapping team to its integer FIFA ranking position.
    """
    table = calculate_group_table(matches)
    teams = list(table["team_id"])
    overall = _overall_keys(table)

    resolved: list[str] = []
    for block in _group_by_key(teams, overall):
        resolved.extend(
            _resolve_head_to_head(
                block, matches, conduct_scores, fifa_ranking_editions
            )
        )
    return resolved


def rank_best_thirds(
    records: pd.DataFrame,
    *,
    fifa_ranking_editions: list[dict[str, float]],
) -> list[str]:
    """Rank the twelve third-placed teams; never uses cross-group head-to-head.

    ``records`` carries one row per third-placed team with ``team_id``,
    ``points``, ``goal_difference``, ``goals_for``, and ``conduct_score``. Any
    ``cross_group_head_to_head_points`` column is deliberately ignored: third
    places come from different groups and never met. Ties fall through to
    conduct score, then successive FIFA-ranking editions.
    """
    overall = {
        row.team_id: (row.points, row.goal_difference, row.goals_for)
        for row in records.itertuples(index=False)
    }
    conduct = {
        row.team_id: row.conduct_score for row in records.itertuples(index=False)
    }
    teams = list(records["team_id"])

    resolved: list[str] = []
    for block in _group_by_key(teams, overall):
        resolved.extend(_resolve_tail(block, conduct, fifa_ranking_editions))
    return resolved


__all__ = [
    "calculate_group_table",
    "rank_best_thirds",
    "rank_group",
]
