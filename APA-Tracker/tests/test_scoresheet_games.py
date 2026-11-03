"""Regression tests for the live data-audit defects (2026-11-03):

1. a player's second game in one team match was dropped (one row per
   (player, match) instead of per scoresheet line);
2. the account's own matches were stored twice (alias rows from the own-team
   pass plus canonical rows from the division pass);
3. the per-game score (racks / points) was discarded;
4. skill-level trends merged a player's 8-ball and 9-ball histories.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.ingest import ingest_match, ingest_match_scores
from database.models import Base, PlayerMatch
from scraper.graphql_scraper import match_player_scores
from scripts import build_coach_advantage_bundle as bundle


def _score(player_id, name, position, win_loss, *, sl=4, eight_wins=None, nine_points=None,
           eight_points=None, nine_match_points=None):
    row = {
        "player": {"id": player_id, "displayName": name},
        "matchPositionNumber": position, "skillLevel": sl, "winLoss": win_loss,
        "eightBallWins": eight_wins, "nineBallPoints": nine_points,
        "eightBallMatchPointsEarned": eight_points, "nineBallMatchPointsEarned": nine_match_points,
    }
    return row


# A real shape: 8-ball team match, five positions, home player 11 shoots twice
# (positions 1 and 5) -- allowed when a team is short-handed.
EIGHT_BALL_MATCH = {
    "id": 90501,
    "home": {"id": 301, "name": "Home Team"},
    "away": {"id": 302, "name": "Away Team"},
    "results": [
        {"homeAway": "HOME", "scores": [
            _score(11, "Twice Shooter", 1, "W", sl=5, eight_wins=4, eight_points=3),
            _score(12, "Home Two", 2, "L", sl=3, eight_wins=1, eight_points=0),
            _score(11, "Twice Shooter", 5, "L", sl=5, eight_wins=2, eight_points=1),
        ]},
        {"homeAway": "AWAY", "scores": [
            _score(21, "Away One", 1, "L", sl=4, eight_wins=1, eight_points=0),
            _score(22, "Away Two", 2, "W", sl=4, eight_wins=3, eight_points=3),
            _score(25, "Away Five", 5, "W", sl=6, eight_wins=5, eight_points=2),
        ]},
    ],
}

NINE_BALL_MATCH = {
    "id": 90601,
    "home": {"id": 301, "name": "Home Team"},
    "away": {"id": 302, "name": "Away Team"},
    "results": [
        {"homeAway": "HOME", "scores": [_score(11, "Twice Shooter", 1, "W", sl=5, nine_points=38, nine_match_points=14)]},
        {"homeAway": "AWAY", "scores": [_score(21, "Away One", 1, "L", sl=4, nine_points=22, nine_match_points=6)]},
    ],
}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()


def _ingest_match(db, match, *, format_, external_id=None):
    ingest_match(
        db, match_id=str(external_id or match["id"]),
        home_team_id="301", away_team_id="302", home_team_name="Home Team", away_team_name="Away Team",
        match_date="2026-10-11T18:00:00-04:00", status="COMPLETED", week=5,
        is_scored=True, is_finalized=True, format=format_, session_name="Fall 2026",
    )


class TestScoresheetParsing:
    def test_every_scoresheet_line_is_a_row_with_its_position(self):
        rows = match_player_scores(EIGHT_BALL_MATCH)
        twice = [r for r in rows if r["player_id"] == "11"]
        assert [r["position"] for r in twice] == [1, 5]
        assert [r["result"] for r in twice] == ["W", "L"]

    def test_eight_ball_game_score_is_carried_from_both_sides(self):
        rows = {(r["player_id"], r["position"]): r for r in match_player_scores(EIGHT_BALL_MATCH)}
        assert rows[("11", 1)]["eight_ball_games_won"] == 4
        assert rows[("11", 1)]["opponent_eight_ball_games_won"] == 1
        assert rows[("11", 1)]["opponent_skill_level"] == 4
        assert rows[("11", 5)]["eight_ball_games_won"] == 2
        assert rows[("11", 5)]["opponent_eight_ball_games_won"] == 5
        assert rows[("11", 1)]["nine_ball_points"] is None

    def test_nine_ball_points_are_carried_from_both_sides(self):
        rows = {r["player_id"]: r for r in match_player_scores(NINE_BALL_MATCH)}
        assert rows["11"]["nine_ball_points"] == 38
        assert rows["11"]["opponent_nine_ball_points"] == 22
        assert rows["11"]["points_earned"] == 14
        assert rows["11"]["eight_ball_games_won"] is None


class TestIngestKeepsEveryGame:
    def test_two_games_by_one_player_in_one_match_are_two_rows(self, db):
        _ingest_match(db, EIGHT_BALL_MATCH, format_="8-Ball Open")
        created, updated = ingest_match_scores(db, "90501", match_player_scores(EIGHT_BALL_MATCH))

        assert (created, updated) == (6, 0)
        rows = db.query(PlayerMatch).join(PlayerMatch.player).filter_by(external_id="11").all()
        assert sorted((r.position, r.result, r.eight_ball_games_won, r.opponent_eight_ball_games_won) for r in rows) == [
            (1, "W", 4, 1), (5, "L", 2, 5),
        ]

    def test_reingesting_the_same_scoresheet_updates_in_place(self, db):
        _ingest_match(db, EIGHT_BALL_MATCH, format_="8-Ball Open")
        ingest_match_scores(db, "90501", match_player_scores(EIGHT_BALL_MATCH))
        created, updated = ingest_match_scores(db, "90501", match_player_scores(EIGHT_BALL_MATCH))

        assert (created, updated) == (0, 6)
        assert db.query(PlayerMatch).count() == 6

    def test_rows_from_an_earlier_alias_ingest_are_removed_once_the_canonical_scoresheet_lands(self, db):
        """The live duplication: the own-team pass stored the match under
        scoresheet alias ids before any roster existed, then the division
        pass stored it again under canonical ids. The current authoritative
        scoresheet must be the only thing left on the match."""
        _ingest_match(db, EIGHT_BALL_MATCH, format_="8-Ball Open")
        alias_rows = [dict(r, player_id="alias-" + r["player_id"]) for r in match_player_scores(EIGHT_BALL_MATCH)]
        ingest_match_scores(db, "90501", alias_rows)
        assert db.query(PlayerMatch).count() == 6

        ingest_match_scores(db, "90501", match_player_scores(EIGHT_BALL_MATCH))

        remaining = db.query(PlayerMatch).join(PlayerMatch.player).all()
        assert len(remaining) == 6
        assert not any(r.player.external_id.startswith("alias-") for r in remaining)

    def test_reconciliation_is_scoped_to_the_one_match(self, db):
        _ingest_match(db, EIGHT_BALL_MATCH, format_="8-Ball Open")
        _ingest_match(db, NINE_BALL_MATCH, format_="9-Ball Open")
        ingest_match_scores(db, "90601", match_player_scores(NINE_BALL_MATCH))
        ingest_match_scores(db, "90501", match_player_scores(EIGHT_BALL_MATCH))

        assert db.query(PlayerMatch).count() == 8  # 6 + 2, nothing cross-deleted


class TestTrendsArePerFormat:
    def test_a_two_format_player_has_two_independent_histories(self, db):
        """APA keeps separate 8-ball and 9-ball skill levels. Merged into one
        series they read as perpetual volatility (observed live: a steady
        SL5 9-ball / SL4 8-ball player showed 'volatility 4, SL 5 -> SL 4')."""
        _ingest_match(db, EIGHT_BALL_MATCH, format_="8-Ball Open")
        _ingest_match(db, NINE_BALL_MATCH, format_="9-Ball Open")
        eight = [dict(r, skill_level=4) for r in match_player_scores(EIGHT_BALL_MATCH)]
        nine = [dict(r, skill_level=5) for r in match_player_scores(NINE_BALL_MATCH)]
        ingest_match_scores(db, "90501", eight)
        ingest_match_scores(db, "90601", nine)
        player_id = db.query(PlayerMatch).join(PlayerMatch.player).filter_by(external_id="11").first().player_id

        trends = bundle._skill_trends(db)

        assert set(k for k in trends if k[0] == player_id) == {(player_id, "8-Ball Open"), (player_id, "9-Ball Open")}
        assert trends[(player_id, "8-Ball Open")].readings == (4, 4)
        assert trends[(player_id, "9-Ball Open")].readings == (5,)
        assert trends[(player_id, "8-Ball Open")].volatility == 0
        assert trends[(player_id, "9-Ball Open")].volatility == 0
