"""Team Analytics: one JSON-serializable document per team, computed from the
database only -- season results, points trajectory against the division,
per-player form, game scores against the race, lineup usage, cross-season
history and lifetime career figures.

A REPORTER over real captured rows. Every number traces to a Match,
PlayerMatch, PlayerTeamHistory, StandingsSnapshot or PlayerCareerStats row;
the only constants are APA's published race charts, and those are checked
against the observed results and the agreement is reported, never assumed.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.models import (
    Match,
    Player,
    PlayerCareerStats,
    PlayerLeagueCareerStats,
    PlayerMatch,
    PlayerTeamHistory,
    StandingsSnapshot,
    Team,
)

SCHEMA = "team-analytics-v1"

# APA published race charts. 8-ball: games needed by (own SL, opponent SL).
# 9-ball: points needed by SL. Reported alongside how many observed winners'
# totals agree with them (analytics never silently trusts a constant).
EIGHT_BALL_RACE: dict[tuple[int, int], tuple[int, int]] = {}
_EIGHT_ROWS = {
    2: {2: (2, 2), 3: (2, 3), 4: (2, 4), 5: (2, 5), 6: (2, 6), 7: (2, 7)},
    3: {2: (3, 2), 3: (2, 2), 4: (2, 3), 5: (2, 4), 6: (2, 5), 7: (2, 6)},
    4: {2: (4, 2), 3: (3, 2), 4: (3, 3), 5: (3, 4), 6: (3, 5), 7: (3, 5)},
    5: {2: (5, 2), 3: (4, 2), 4: (4, 3), 5: (4, 4), 6: (4, 5), 7: (4, 5)},
    6: {2: (6, 2), 3: (5, 2), 4: (5, 3), 5: (5, 4), 6: (5, 5), 7: (5, 6)},
    7: {2: (7, 2), 3: (6, 2), 4: (5, 3), 5: (5, 4), 6: (6, 5), 7: (5, 5)},
}
for _own, _row in _EIGHT_ROWS.items():
    for _opp, _race in _row.items():
        EIGHT_BALL_RACE[(_own, _opp)] = _race

NINE_BALL_POINTS: dict[int, int] = {1: 14, 2: 19, 3: 25, 4: 31, 5: 38, 6: 46, 7: 55, 8: 65, 9: 75}


def game_format(raw: Optional[str]) -> Optional[str]:
    """'eight' / 'nine' from any captured format label ('8-Ball Open',
    'EIGHT', 'NINE_BALL', ...), or None when it names neither."""
    if not raw:
        return None
    text = str(raw).lower()
    if "9" in text or "nine" in text:
        return "nine"
    if "8" in text or "eight" in text:
        return "eight"
    return None


def race_targets(fmt: Optional[str], own_sl: Optional[int], opp_sl: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    """(own target, opponent target) from the published chart, or Nones."""
    if fmt == "eight" and own_sl is not None and opp_sl is not None:
        return EIGHT_BALL_RACE.get((int(own_sl), int(opp_sl)), (None, None))
    if fmt == "nine":
        return (
            NINE_BALL_POINTS.get(int(own_sl)) if own_sl is not None else None,
            NINE_BALL_POINTS.get(int(opp_sl)) if opp_sl is not None else None,
        )
    return (None, None)


_SEASON_ORDER = {"spring": 1, "summer": 2, "fall": 3, "autumn": 3, "winter": 0}


def session_sort_key(name: Optional[str]) -> tuple[int, int, str]:
    """Chronological key for 'Fall 2026', '2026 Summer', 'Spring 2025'..."""
    text = (name or "").strip()
    year = re.search(r"(19|20)\d{2}", text)
    season = next((v for k, v in _SEASON_ORDER.items() if k in text.lower()), 9)
    return (int(year.group(0)) if year else 0, season, text)


def _norm_name(name: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _pct(wins: int, played: int) -> Optional[float]:
    return round(wins / played, 4) if played else None


def _score_text(fmt: Optional[str], own: Optional[int], opp: Optional[int]) -> Optional[str]:
    if own is None or opp is None:
        return None
    return f"{own}-{opp}"


@dataclass
class _TeamContext:
    external_id: str
    name: str
    session_name: Optional[str]
    format: Optional[str]
    division_id: Optional[str]


def _team_context(db: Session, team_external_id: str) -> _TeamContext:
    team = db.query(Team).filter_by(external_id=str(team_external_id)).one_or_none()
    history = (
        db.query(PlayerTeamHistory)
        .filter_by(team_external_id=str(team_external_id))
        .order_by(PlayerTeamHistory.is_current.desc(), PlayerTeamHistory.id.desc())
        .all()
    )
    session_name = next((h.session_name for h in history if h.session_name), None)
    division_id = next((h.division_id for h in history if h.division_id), None)
    sample = (
        db.query(Match)
        .filter((Match.home_team_id == str(team_external_id)) | (Match.away_team_id == str(team_external_id)))
        .filter(Match.format.isnot(None))
        .first()
    )
    name = team.name if team else next((h.team_name for h in history if h.team_name), str(team_external_id))
    if session_name is None and sample is not None:
        session_name = sample.session_name
    return _TeamContext(
        external_id=str(team_external_id), name=name, session_name=session_name,
        format=sample.format if sample else None, division_id=division_id,
    )


def _team_matches(db: Session, team_external_id: str, session_name: Optional[str]) -> list[Match]:
    query = db.query(Match).filter(
        (Match.home_team_id == team_external_id) | (Match.away_team_id == team_external_id),
        Match.is_bye.is_(False),
    )
    if session_name:
        query = query.filter(Match.session_name == session_name)
    return query.order_by(Match.week, Match.match_date, Match.external_id).all()


def _match_result(match: Match, team_external_id: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    home = match.home_team_id == team_external_id
    ours, theirs = (match.home_score, match.away_score) if home else (match.away_score, match.home_score)
    if ours is None or theirs is None:
        return None, ours, theirs
    return ("W" if ours > theirs else "L" if ours < theirs else "T"), ours, theirs


def _season(db: Session, ctx: _TeamContext, matches: list[Match]) -> dict[str, Any]:
    fmt = game_format(ctx.format)
    weeks = []
    record = {"wins": 0, "losses": 0, "ties": 0, "played": 0, "scheduled": len(matches), "pending": 0}
    points = {"for": 0.0, "against": 0.0}
    home_away = {
        "home": {"played": 0, "wins": 0, "points_for": 0.0, "points_against": 0.0},
        "away": {"played": 0, "wins": 0, "points_for": 0.0, "points_against": 0.0},
    }
    for match in matches:
        is_home = match.home_team_id == ctx.external_id
        opponent_name = match.away_team_name if is_home else match.home_team_name
        opponent_id = match.away_team_id if is_home else match.home_team_id
        result, ours, theirs = _match_result(match, ctx.external_id)
        rows = [pm for pm in match.player_matches if pm.team_id == ctx.external_id]
        games_won = sum(1 for pm in rows if pm.result == "W")
        pending = bool(match.is_scored) and not rows and result is None
        if pending:
            record["pending"] += 1
        if result is not None:
            record["played"] += 1
            record["wins" if result == "W" else "losses" if result == "L" else "ties"] += 1
            points["for"] += float(ours)
            points["against"] += float(theirs)
            side = home_away["home" if is_home else "away"]
            side["played"] += 1
            side["wins"] += 1 if result == "W" else 0
            side["points_for"] += float(ours)
            side["points_against"] += float(theirs)
        weeks.append({
            "week": match.week, "date": match.match_date, "match_id": match.external_id,
            "opponent": opponent_name, "opponent_id": opponent_id, "home": is_home,
            "our_score": ours, "their_score": theirs, "result": result,
            "status": match.status, "scored": bool(match.is_scored), "finalized": bool(match.is_finalized),
            "pending_scoresheet": pending, "games_won": games_won if rows else None,
            "games_played": len(rows) if rows else None,
        })
    for side in home_away.values():
        side["win_pct"] = _pct(side["wins"], side["played"])
    record["win_pct"] = _pct(record["wins"], record["played"])

    standing = None
    latest = db.query(StandingsSnapshot).filter_by(team_name=ctx.name).order_by(StandingsSnapshot.captured_at.desc()).first()
    if latest is not None:
        division_rows = db.query(StandingsSnapshot).filter_by(captured_at=latest.captured_at).all()
        standing = {
            "rank": latest.rank, "points": latest.points, "teams": len(division_rows),
            "captured_at": latest.captured_at.isoformat() if latest.captured_at else None,
        }
    return {
        "format": fmt, "record": record, "points": points, "standing": standing,
        "weeks": weeks, "home_away": home_away,
    }


def _division_team_ids(db: Session, ctx: _TeamContext) -> list[str]:
    if ctx.division_id and ctx.session_name:
        rows = (
            db.query(PlayerTeamHistory.team_external_id)
            .filter_by(division_id=ctx.division_id, session_name=ctx.session_name)
            .distinct().all()
        )
        ids = sorted({r[0] for r in rows if r[0]})
        if ids:
            return ids
    ids = {ctx.external_id}
    for m in _team_matches(db, ctx.external_id, ctx.session_name):
        ids.add(m.away_team_id if m.home_team_id == ctx.external_id else m.home_team_id)
    return sorted(i for i in ids if i)


def _trajectory(db: Session, ctx: _TeamContext) -> dict[str, Any]:
    """Cumulative team points per week for every team in the division, from
    the scored matches themselves -- standings snapshots only exist per
    refresh, matches exist per week."""
    team_ids = _division_team_ids(db, ctx)
    query = db.query(Match).filter(Match.is_bye.is_(False), Match.home_score.isnot(None), Match.away_score.isnot(None))
    if ctx.session_name:
        query = query.filter(Match.session_name == ctx.session_name)
    matches = [m for m in query.all() if m.home_team_id in team_ids and m.away_team_id in team_ids]
    if not matches:
        return {"weeks": [], "teams": []}
    weeks = sorted({m.week for m in matches if m.week is not None})
    names: dict[str, str] = {}
    per_week: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for m in matches:
        names.setdefault(m.home_team_id, m.home_team_name)
        names.setdefault(m.away_team_id, m.away_team_name)
        if m.week is None:
            continue
        per_week[m.home_team_id][m.week] += float(m.home_score)
        per_week[m.away_team_id][m.week] += float(m.away_score)
    teams = []
    for team_id in team_ids:
        running, series = 0.0, []
        for w in weeks:
            running += per_week[team_id].get(w, 0.0)
            series.append(round(running, 2))
        teams.append({
            "team_id": team_id, "name": names.get(team_id, team_id),
            "is_us": team_id == ctx.external_id, "cumulative": series,
        })
    teams.sort(key=lambda t: (-t["cumulative"][-1] if t["cumulative"] else 0, t["name"]))
    return {"weeks": weeks, "teams": teams}


def _roster(db: Session, ctx: _TeamContext) -> list[PlayerTeamHistory]:
    query = db.query(PlayerTeamHistory).filter_by(team_external_id=ctx.external_id)
    if ctx.session_name:
        query = query.filter_by(session_name=ctx.session_name)
    rows = query.all()
    seen: dict[int, PlayerTeamHistory] = {}
    for row in rows:
        if row.player_id not in seen or (row.is_current and not seen[row.player_id].is_current):
            seen[row.player_id] = row
    return sorted(seen.values(), key=lambda r: (r.player.name if r.player else ""))


def _player_lines(db: Session, ctx: _TeamContext, player_id: int, fmt: Optional[str]) -> list[dict[str, Any]]:
    rows = (
        db.query(PlayerMatch)
        .join(Match, PlayerMatch.match_id == Match.id)
        .filter(PlayerMatch.player_id == player_id, PlayerMatch.team_id == ctx.external_id)
        .filter(Match.session_name == ctx.session_name if ctx.session_name else True)
        .order_by(Match.week, PlayerMatch.match_date, PlayerMatch.position)
        .all()
    )
    lines = []
    for pm in rows:
        match = pm.match
        own_games = pm.eight_ball_games_won if fmt == "eight" else pm.nine_ball_points
        opp_games = pm.opponent_eight_ball_games_won if fmt == "eight" else pm.opponent_nine_ball_points
        own_target, opp_target = race_targets(fmt, pm.skill_level, pm.opponent_skill_level)
        margin = None
        if own_games is not None and opp_games is not None and own_target and opp_target:
            margin = round(own_games / own_target - opp_games / opp_target, 4)
        lines.append({
            "week": match.week if match else None, "date": pm.match_date, "position": pm.position,
            "opponent_team": pm.opponent, "result": pm.result, "skill_level": pm.skill_level,
            "opponent_skill_level": pm.opponent_skill_level,
            "own": own_games, "opp": opp_games, "own_target": own_target, "opp_target": opp_target,
            "score": _score_text(fmt, own_games, opp_games), "margin": margin,
            "points_earned": pm.points_earned,
            "on_break": pm.eight_on_break if fmt == "eight" else pm.nine_on_snap,
            "break_and_run": pm.eight_break_and_run if fmt == "eight" else pm.nine_break_and_run,
            "home": bool(match and match.home_team_id == ctx.external_id),
        })
    return lines


def _players(db: Session, ctx: _TeamContext, fmt: Optional[str]) -> list[dict[str, Any]]:
    players = []
    for roster_row in _roster(db, ctx):
        player: Player = roster_row.player
        lines = _player_lines(db, ctx, roster_row.player_id, fmt)
        wins = sum(1 for l in lines if l["result"] == "W")
        losses = sum(1 for l in lines if l["result"] == "L")
        margins = [l["margin"] for l in lines if l["margin"] is not None]
        points = [l["points_earned"] for l in lines if l["points_earned"] is not None]
        by_delta: dict[int, dict[str, int]] = defaultdict(lambda: {"games": 0, "wins": 0})
        for l in lines:
            if l["skill_level"] is not None and l["opponent_skill_level"] is not None:
                bucket = by_delta[int(l["opponent_skill_level"]) - int(l["skill_level"])]
                bucket["games"] += 1
                bucket["wins"] += 1 if l["result"] == "W" else 0
        home = [l for l in lines if l["home"]]
        away = [l for l in lines if not l["home"]]
        players.append({
            "player_id": roster_row.player_id, "external_id": player.external_id if player else None,
            "name": player.name if player else "", "skill_level": roster_row.skill_level,
            "apa_won": roster_row.matches_won, "apa_played": roster_row.matches_played,
            "games": len(lines), "wins": wins, "losses": losses, "win_pct": _pct(wins, len(lines)),
            "avg_margin": round(sum(margins) / len(margins), 4) if margins else None,
            "avg_points": round(sum(points) / len(points), 2) if points else None,
            "on_break": sum(l["on_break"] or 0 for l in lines), "break_and_run": sum(l["break_and_run"] or 0 for l in lines),
            "home": {"games": len(home), "wins": sum(1 for l in home if l["result"] == "W")},
            "away": {"games": len(away), "wins": sum(1 for l in away if l["result"] == "W")},
            "vs_skill_delta": [
                {"delta": d, "games": v["games"], "wins": v["wins"], "win_pct": _pct(v["wins"], v["games"])}
                for d, v in sorted(by_delta.items())
            ],
            "skill_readings": [
                {"week": l["week"], "date": l["date"], "skill_level": l["skill_level"]}
                for l in lines if l["skill_level"] is not None
            ],
            "lines": lines,
        })
    return players


def _race_check(players: list[dict[str, Any]], fmt: Optional[str]) -> dict[str, Any]:
    agree = total = 0
    for p in players:
        for l in p["lines"]:
            if l["result"] != "W" or l["own"] is None or l["own_target"] is None:
                continue
            total += 1
            agree += 1 if l["own"] == l["own_target"] else 0
    chart: Any
    if fmt == "eight":
        chart = {f"{own}-{opp}": list(race) for (own, opp), race in sorted(EIGHT_BALL_RACE.items())}
    elif fmt == "nine":
        chart = {str(sl): pts for sl, pts in NINE_BALL_POINTS.items()}
    else:
        chart = {}
    return {"format": fmt, "chart": chart, "winners_checked": total, "winners_agreeing": agree, "source": "APA published race chart"}


def _lineup(players: list[dict[str, Any]], weeks: list[dict[str, Any]]) -> dict[str, Any]:
    week_numbers = [w["week"] for w in weeks if w["week"] is not None]
    rows = []
    for p in players:
        cells: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for l in p["lines"]:
            if l["week"] is not None:
                cells[l["week"]].append({"result": l["result"], "score": l["score"], "position": l["position"]})
        rows.append({"name": p["name"], "skill_level": p["skill_level"], "cells": [cells.get(w, []) for w in week_numbers]})
    return {"weeks": week_numbers, "rows": rows}


def _lineage(db: Session, ctx: _TeamContext) -> list[dict[str, Any]]:
    target = _norm_name(ctx.name)
    rows = db.query(PlayerTeamHistory).all()
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if _norm_name(row.team_name) != target or not row.team_external_id:
            continue
        key = (row.team_external_id, row.session_name or "")
        entry = seen.setdefault(key, {
            "team_external_id": row.team_external_id, "session_name": row.session_name,
            "division_id": row.division_id, "rank": None, "is_current": False,
        })
        entry["is_current"] = entry["is_current"] or bool(row.is_current)
        if row.rank is not None:
            entry["rank"] = row.rank
    lineage = list(seen.values())
    if ctx.external_id not in {e["team_external_id"] for e in lineage}:
        lineage.append({"team_external_id": ctx.external_id, "session_name": ctx.session_name,
                        "division_id": ctx.division_id, "rank": None, "is_current": True})
    lineage.sort(key=lambda e: session_sort_key(e["session_name"]))
    return lineage


def _history(db: Session, ctx: _TeamContext, lineage: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions = []
    for entry in lineage:
        team_id = entry["team_external_id"]
        matches = _team_matches(db, team_id, entry["session_name"])
        fmt = game_format(matches[0].format) if matches else None
        wins = losses = ties = 0
        pf = pa = 0.0
        for m in matches:
            result, ours, theirs = _match_result(m, team_id)
            if result is None:
                continue
            wins += result == "W"; losses += result == "L"; ties += result == "T"
            pf += float(ours); pa += float(theirs)
        per_player: dict[int, dict[str, Any]] = {}
        for m in matches:
            for pm in m.player_matches:
                if pm.team_id != team_id or pm.player is None:
                    continue
                p = per_player.setdefault(pm.player_id, {"name": pm.player.name, "games": 0, "wins": 0, "skill_levels": []})
                p["games"] += 1
                p["wins"] += 1 if pm.result == "W" else 0
                if pm.skill_level is not None:
                    p["skill_levels"].append(pm.skill_level)
        players = []
        for p in per_player.values():
            players.append({
                "name": p["name"], "games": p["games"], "wins": p["wins"], "win_pct": _pct(p["wins"], p["games"]),
                "skill_level_start": p["skill_levels"][0] if p["skill_levels"] else None,
                "skill_level_end": p["skill_levels"][-1] if p["skill_levels"] else None,
            })
        players.sort(key=lambda p: (-p["games"], p["name"]))
        sessions.append({
            "session_name": entry["session_name"], "team_external_id": team_id, "format": fmt,
            "division_id": entry["division_id"], "is_current": entry["is_current"],
            "matches_scheduled": len(matches), "wins": wins, "losses": losses, "ties": ties,
            "win_pct": _pct(wins, wins + losses + ties), "points_for": pf, "points_against": pa,
            "final_rank": entry["rank"], "players": players,
        })
    return sessions


def _career(db: Session, players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [p["player_id"] for p in players]
    if not ids:
        return []
    names = {p["player_id"]: p["name"] for p in players}
    rows = []
    for row in db.query(PlayerCareerStats).filter(PlayerCareerStats.player_id.in_(ids)).all():
        rows.append({
            "name": names.get(row.player_id), "format": game_format(row.format), "scope": "lifetime",
            "matches_won": row.matches_won, "matches_played": row.matches_played,
            "win_pct": _pct(row.matches_won or 0, row.matches_played or 0),
            "cla": row.cla, "defensive_shot_avg": row.defensive_shot_avg, "last_played": row.last_played,
            "matches_last_two_years": row.match_count_last_two_yrs,
            "on_break": row.on_break_count, "break_and_runs": row.break_and_runs, "mini_slams": row.mini_slams,
            "rackless": row.rackless, "skunks": row.skunks,
        })
    for row in db.query(PlayerLeagueCareerStats).filter(PlayerLeagueCareerStats.player_id.in_(ids)).all():
        rows.append({
            "name": names.get(row.player_id), "format": game_format(row.format), "scope": f"league {row.league_slug or row.league_id}",
            "matches_won": row.matches_won, "matches_played": row.matches_played,
            "win_pct": _pct(row.matches_won or 0, row.matches_played or 0),
            "cla": row.cla, "defensive_shot_avg": row.defensive_shot_avg, "last_played": row.last_played,
            "matches_last_two_years": row.match_count_last_two_yrs,
            "on_break": row.on_break_count, "break_and_runs": row.break_and_runs, "mini_slams": row.mini_slams,
            "rackless": row.rackless, "skunks": row.skunks,
        })
    rows.sort(key=lambda r: (r["name"] or "", r["format"] or "", r["scope"]))
    return rows


def build_team_analytics(db: Session, team_external_id: str) -> dict[str, Any]:
    ctx = _team_context(db, str(team_external_id))
    matches = _team_matches(db, ctx.external_id, ctx.session_name)
    season = _season(db, ctx, matches)
    fmt = season["format"]
    players = _players(db, ctx, fmt)
    lineage = _lineage(db, ctx)
    return {
        "schema": SCHEMA,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "team": {
            "external_id": ctx.external_id, "name": ctx.name, "session_name": ctx.session_name,
            "format": ctx.format, "game": fmt, "division_id": ctx.division_id,
        },
        "season": season,
        "trajectory": _trajectory(db, ctx),
        "players": players,
        "race": _race_check(players, fmt),
        "lineup": _lineup(players, season["weeks"]),
        "history": _history(db, ctx, lineage),
        "career": _career(db, players),
    }
