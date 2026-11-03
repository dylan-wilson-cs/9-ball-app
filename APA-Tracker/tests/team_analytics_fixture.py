"""A small, realistic two-season database for the Team Analytics tests.

Our team "Fixture Experts" plays 9-ball in a four-team division. Fall 2026 has
three scored weeks with full per-line scoresheets (one player shoots twice in
week 2), one scored week APA has not posted yet, and one unplayed week. Spring
2026 is a finished prior season under a different team id, same team name.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.ingest import (
    ingest_eight_ball_stats,
    ingest_head_to_head,
    ingest_match,
    ingest_match_scores,
    ingest_player_team_history,
    ingest_standings,
    upsert_player,
    upsert_team,
)
from database.models import Base

OUR_ID, OUR_NAME = "7001", "Fixture Experts"
PRIOR_ID = "6001"  # same team name, Spring 2026
DIVISION, PRIOR_DIVISION = "440", "430"
FORMAT = "9-Ball Open"
TEAMS = {OUR_ID: OUR_NAME, "7002": "Rack Pack", "7003": "Side Pocket", "7004": "Nine Lives"}
PRIOR_TEAMS = {PRIOR_ID: OUR_NAME, "6002": "Rack Pack", "6003": "Side Pocket", "6004": "Nine Lives"}

# (external id, name, SL) -- SL per team session
OUR_ROSTER = [("P1", "Ann Fixture", 5), ("P2", "Bo Sample", 4), ("P3", "Cy Demo", 3), ("P4", "Di Stub", 6), ("P5", "Ed Mock", 2)]
OPP_ROSTER = {
    "7002": [("Q1", "Opp One", 4), ("Q2", "Opp Two", 5), ("Q3", "Opp Three", 3), ("Q4", "Opp Four", 6), ("Q5", "Opp Five", 2)],
    "7003": [("R1", "Side One", 5), ("R2", "Side Two", 4), ("R3", "Side Three", 3), ("R4", "Side Four", 7), ("R5", "Side Five", 2)],
    "7004": [("S1", "Nine One", 4), ("S2", "Nine Two", 4), ("S3", "Nine Three", 3), ("S4", "Nine Four", 5), ("S5", "Nine Five", 2)],
}


def _line(pid, name, pos, sl, points, match_points, win):
    return {"player": {"id": pid, "displayName": name}, "matchPositionNumber": pos, "skillLevel": sl,
            "winLoss": "W" if win else "L", "nineBallPoints": points, "nineBallMatchPointsEarned": match_points,
            "nineOnSnap": 1 if win and pos == 1 else 0, "nineBallBreakAndRun": 0}


def _detail(match_id, home_id, away_id, home_lines, away_lines):
    return {
        "id": int(match_id),
        "home": {"id": int(home_id), "name": TEAMS.get(home_id) or PRIOR_TEAMS.get(home_id)},
        "away": {"id": int(away_id), "name": TEAMS.get(away_id) or PRIOR_TEAMS.get(away_id)},
        "results": [{"homeAway": "HOME", "scores": home_lines}, {"homeAway": "AWAY", "scores": away_lines}],
    }


def _roster_rows(db, teams, roster_by_team, division, session, current):
    for team_id, name in teams.items():
        team = upsert_team(db, team_id, name)
        for ext, pname, sl in roster_by_team[team_id]:
            player = upsert_player(db, ext, pname, team)
            ingest_player_team_history(db, player, [{
                "team_id": team_id, "team_name": name, "division_id": division, "session_name": session,
                "is_current": current, "skill_level": sl, "matches_won": None, "matches_played": None,
                "rank": 1 if team_id in (OUR_ID, PRIOR_ID) else None,
            }])


def _match(db, mid, week, date, home, away, session, home_pts=None, away_pts=None, scored=True, finalized=True, status="COMPLETED"):
    ingest_match(
        db, match_id=mid, home_team_id=home, away_team_id=away,
        home_team_name=TEAMS.get(home) or PRIOR_TEAMS.get(home), away_team_name=TEAMS.get(away) or PRIOR_TEAMS.get(away),
        match_date=date, status=status, week=week, is_bye=False, is_scored=scored, is_finalized=finalized,
        home_score=home_pts, away_score=away_pts, format=FORMAT, session_name=session,
    )


def build(path) -> str:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        # ---- Spring 2026 (prior season, finished) ----
        prior_roster = {PRIOR_ID: [("P1", "Ann Fixture", 4), ("P2", "Bo Sample", 4), ("P3", "Cy Demo", 3)],
                        "6002": OPP_ROSTER["7002"], "6003": OPP_ROSTER["7003"], "6004": OPP_ROSTER["7004"]}
        _roster_rows(db, PRIOR_TEAMS, prior_roster, PRIOR_DIVISION, "Spring 2026", current=False)
        _match(db, "60001", 1, "2026-03-01T18:00:00-05:00", PRIOR_ID, "6002", "Spring 2026", 70, 50)
        _match(db, "60002", 2, "2026-03-08T18:00:00-05:00", "6003", PRIOR_ID, "Spring 2026", 61, 59)
        d = _detail("60001", PRIOR_ID, "6002",
                    [_line("P1", "Ann Fixture", 1, 4, 31, 14, True), _line("P2", "Bo Sample", 2, 4, 20, 6, False)],
                    [_line("Q1", "Opp One", 1, 4, 18, 6, False), _line("Q2", "Opp Two", 2, 5, 38, 14, True)])
        from scraper.graphql_scraper import head_to_head_rows, match_player_scores
        ingest_match_scores(db, "60001", match_player_scores(d)); ingest_head_to_head(db, "60001", head_to_head_rows(d))

        # ---- Fall 2026 (current) ----
        roster = {OUR_ID: OUR_ROSTER, **OPP_ROSTER}
        _roster_rows(db, TEAMS, roster, DIVISION, "Fall 2026", current=True)
        # week 1: home vs Rack Pack, win 72-48
        _match(db, "70001", 1, "2026-09-13T18:00:00-04:00", OUR_ID, "7002", "Fall 2026", 72, 48)
        _match(db, "70011", 1, "2026-09-13T18:00:00-04:00", "7003", "7004", "Fall 2026", 55, 65)
        d1 = _detail("70001", OUR_ID, "7002",
            [_line("P1", "Ann Fixture", 1, 5, 38, 14, True), _line("P2", "Bo Sample", 2, 4, 31, 15, True),
             _line("P3", "Cy Demo", 3, 3, 25, 16, True), _line("P4", "Di Stub", 4, 6, 30, 5, False),
             _line("P5", "Ed Mock", 5, 2, 19, 20, True)],
            [_line("Q1", "Opp One", 1, 4, 20, 6, False), _line("Q2", "Opp Two", 2, 5, 25, 5, False),
             _line("Q3", "Opp Three", 3, 3, 12, 4, False), _line("Q4", "Opp Four", 4, 6, 46, 15, True),
             _line("Q5", "Opp Five", 5, 2, 0, 0, False)])
        ingest_match_scores(db, "70001", match_player_scores(d1)); ingest_head_to_head(db, "70001", head_to_head_rows(d1))
        # week 2: away at Side Pocket, loss 52-68; Ann shoots twice (positions 1 and 5)
        _match(db, "70002", 2, "2026-09-20T18:00:00-04:00", "7003", OUR_ID, "Fall 2026", 68, 52)
        _match(db, "70012", 2, "2026-09-20T18:00:00-04:00", "7002", "7004", "Fall 2026", 60, 60)
        d2 = _detail("70002", "7003", OUR_ID,
            [_line("R1", "Side One", 1, 5, 38, 14, True), _line("R2", "Side Two", 2, 4, 31, 14, True),
             _line("R3", "Side Three", 3, 3, 10, 3, False), _line("R4", "Side Four", 4, 7, 55, 17, True),
             _line("R5", "Side Five", 5, 2, 7, 3, False)],
            [_line("P1", "Ann Fixture", 1, 5, 30, 6, False), _line("P2", "Bo Sample", 2, 4, 22, 6, False),
             _line("P3", "Cy Demo", 3, 3, 25, 17, True), _line("P4", "Di Stub", 4, 6, 20, 3, False),
             _line("P1", "Ann Fixture", 5, 5, 38, 17, True)])
        ingest_match_scores(db, "70002", match_player_scores(d2)); ingest_head_to_head(db, "70002", head_to_head_rows(d2))
        # week 3: home vs Nine Lives, win 65-55
        _match(db, "70003", 3, "2026-09-27T18:00:00-04:00", OUR_ID, "7004", "Fall 2026", 65, 55)
        _match(db, "70013", 3, "2026-09-27T18:00:00-04:00", "7002", "7003", "Fall 2026", 58, 62)
        d3 = _detail("70003", OUR_ID, "7004",
            [_line("P1", "Ann Fixture", 1, 4, 31, 14, True), _line("P2", "Bo Sample", 2, 4, 31, 14, True),
             _line("P3", "Cy Demo", 3, 3, 15, 5, False), _line("P4", "Di Stub", 4, 6, 46, 14, True),
             _line("P5", "Ed Mock", 5, 2, 10, 4, False)],
            [_line("S1", "Nine One", 1, 4, 20, 6, False), _line("S2", "Nine Two", 2, 4, 25, 6, False),
             _line("S3", "Nine Three", 3, 3, 25, 15, True), _line("S4", "Nine Four", 4, 5, 20, 6, False),
             _line("S5", "Nine Five", 5, 2, 19, 16, True)])
        ingest_match_scores(db, "70003", match_player_scores(d3)); ingest_head_to_head(db, "70003", head_to_head_rows(d3))
        # week 4: played, APA has not posted (scored flag, no points, no sheet)
        _match(db, "70004", 4, "2026-10-04T18:00:00-04:00", "7002", OUR_ID, "Fall 2026", None, None, scored=True, finalized=False)
        # week 5: unplayed
        _match(db, "70005", 5, "2026-10-11T18:00:00-04:00", OUR_ID, "7003", "Fall 2026", None, None, scored=False, finalized=False, status="UNPLAYED")

        ingest_standings(db, [
            {"team_name": OUR_NAME, "rank": 1, "wins": None, "losses": None, "points": 189.0},
            {"team_name": "Side Pocket", "rank": 2, "wins": None, "losses": None, "points": 185.0},
            {"team_name": "Nine Lives", "rank": 3, "wins": None, "losses": None, "points": 180.0},
            {"team_name": "Rack Pack", "rank": 4, "wins": None, "losses": None, "points": 166.0},
        ])
        from database.models import Player
        ann = db.query(Player).filter_by(external_id="P1").one()
        ingest_eight_ball_stats(db, ann, {
            "alias_id": 1, "display_name": "Ann Fixture",
            "eight_ball_matches_won": None, "eight_ball_matches_played": None, "eight_ball_cla": None,
            "eight_ball_defensive_shot_avg": None, "eight_ball_match_count_for_last_two_yrs": None,
            "eight_ball_last_played": None, "eight_ball_on_break_count": None, "eight_ball_break_and_runs": None,
            "eight_ball_rackless": None, "eight_ball_mini_slams": None,
            "nine_ball_matches_won": 45, "nine_ball_matches_played": 85, "nine_ball_cla": 4,
            "nine_ball_defensive_shot_avg": 1.2, "nine_ball_match_count_for_last_two_yrs": 40,
            "nine_ball_last_played": "2026-09-27", "nine_ball_on_break_count": 6, "nine_ball_break_and_runs": 2,
            "nine_ball_mini_slams": 1, "nine_ball_skunks": 0,
        })
        db.commit()
    engine.dispose()
    return str(path)
