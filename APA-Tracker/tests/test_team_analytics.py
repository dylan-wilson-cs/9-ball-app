from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from analytics import team_analytics as ta
from tests.team_analytics_fixture import OUR_ID, OUR_NAME, build


@pytest.fixture(scope="module")
def doc(tmp_path_factory):
    path = build(tmp_path_factory.mktemp("ta") / "fixture.db")
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as db:
        yield ta.build_team_analytics(db, OUR_ID)
    engine.dispose()


class TestRaceCharts:
    def test_eight_ball_chart_is_symmetric(self):
        for (a, b), (ra, rb) in ta.EIGHT_BALL_RACE.items():
            assert ta.EIGHT_BALL_RACE[(b, a)] == (rb, ra)

    def test_targets_by_format(self):
        assert ta.race_targets("eight", 5, 3) == (4, 2)
        assert ta.race_targets("nine", 5, 3) == (38, 25)
        assert ta.race_targets("nine", None, 3) == (None, 25)
        assert ta.race_targets(None, 5, 3) == (None, None)

    def test_format_detection(self):
        assert ta.game_format("8-Ball Open") == "eight"
        assert ta.game_format("NINE") == "nine"
        assert ta.game_format("EIGHT_BALL") == "eight"
        assert ta.game_format(None) is None

    def test_session_order(self):
        names = ["Fall 2026", "Spring 2025", "2026 Summer", "Fall 2025"]
        assert sorted(names, key=ta.session_sort_key) == ["Spring 2025", "Fall 2025", "2026 Summer", "Fall 2026"]


class TestSeason:
    def test_team_identity_and_format(self, doc):
        assert doc["schema"] == ta.SCHEMA
        assert doc["team"] == {
            "external_id": OUR_ID, "name": OUR_NAME, "session_name": "Fall 2026",
            "format": "9-Ball Open", "game": "nine", "division_id": "440",
        }

    def test_record_points_and_pending(self, doc):
        s = doc["season"]
        assert s["record"] == {"wins": 2, "losses": 1, "ties": 0, "played": 3, "scheduled": 5, "pending": 1, "win_pct": 0.6667}
        assert s["points"] == {"for": 189.0, "against": 171.0}
        assert [w["result"] for w in s["weeks"]] == ["W", "L", "W", None, None]
        assert s["weeks"][3]["pending_scoresheet"] is True and s["weeks"][4]["pending_scoresheet"] is False
        assert s["weeks"][1]["games_won"] == 2 and s["weeks"][1]["games_played"] == 5

    def test_home_away_split(self, doc):
        ha = doc["season"]["home_away"]
        assert ha["home"] == {"played": 2, "wins": 2, "points_for": 137.0, "points_against": 103.0, "win_pct": 1.0}
        assert ha["away"] == {"played": 1, "wins": 0, "points_for": 52.0, "points_against": 68.0, "win_pct": 0.0}

    def test_standing_from_latest_snapshot(self, doc):
        assert doc["season"]["standing"]["rank"] == 1
        assert doc["season"]["standing"]["teams"] == 4


class TestTrajectory:
    def test_every_division_team_has_cumulative_points_per_week(self, doc):
        t = doc["trajectory"]
        assert t["weeks"] == [1, 2, 3]
        by_name = {x["name"]: x for x in t["teams"]}
        assert by_name[OUR_NAME]["is_us"] is True
        assert by_name[OUR_NAME]["cumulative"] == [72.0, 124.0, 189.0]
        assert by_name["Side Pocket"]["cumulative"] == [55.0, 123.0, 185.0]
        assert [x["name"] for x in t["teams"]][0] == OUR_NAME  # leader first


class TestPlayers:
    def test_a_double_shooter_keeps_both_games(self, doc):
        ann = next(p for p in doc["players"] if p["name"] == "Ann Fixture")
        assert ann["games"] == 4 and ann["wins"] == 3 and ann["losses"] == 1
        week2 = [l for l in ann["lines"] if l["week"] == 2]
        assert [(l["position"], l["result"]) for l in week2] == [(1, "L"), (5, "W")]

    def test_nine_ball_score_and_margin_against_the_race(self, doc):
        ann = next(p for p in doc["players"] if p["name"] == "Ann Fixture")
        first = ann["lines"][0]
        assert first["score"] == "38-20"
        assert (first["own_target"], first["opp_target"]) == (38, 31)
        assert first["margin"] == round(38 / 38 - 20 / 31, 4)

    def test_skill_readings_are_this_team_only(self, doc):
        ann = next(p for p in doc["players"] if p["name"] == "Ann Fixture")
        assert [r["skill_level"] for r in ann["skill_readings"]] == [5, 5, 5, 4]  # no Spring 2026 SL4 readings mixed in

    def test_vs_skill_delta_buckets(self, doc):
        ann = next(p for p in doc["players"] if p["name"] == "Ann Fixture")
        buckets = {b["delta"]: b for b in ann["vs_skill_delta"]}
        assert buckets[-1] == {"delta": -1, "games": 1, "wins": 1, "win_pct": 1.0}   # SL5 vs SL4 (w1)
        assert buckets[-3] == {"delta": -3, "games": 1, "wins": 1, "win_pct": 1.0}   # SL5 vs SL2 (w2 pos 5)
        assert buckets[0] == {"delta": 0, "games": 2, "wins": 1, "win_pct": 0.5}     # SL5 vs SL5 (w2 L), SL4 vs SL4 (w3 W)

    def test_counts_and_rates(self, doc):
        by_name = {p["name"]: p for p in doc["players"]}
        assert by_name["Ed Mock"]["games"] == 2 and by_name["Ed Mock"]["win_pct"] == 0.5
        assert by_name["Ann Fixture"]["on_break"] == 2  # position-1 wins in weeks 1 and 3
        assert by_name["Ann Fixture"]["home"] == {"games": 2, "wins": 2}
        assert by_name["Ann Fixture"]["away"] == {"games": 2, "wins": 1}
        assert by_name["Di Stub"]["skill_level"] == 6


class TestRaceCheck:
    def test_winners_are_checked_against_the_chart(self, doc):
        race = doc["race"]
        assert race["format"] == "nine"
        assert race["winners_checked"] == 9   # our 9 winning lines across 3 weeks
        assert race["winners_agreeing"] == 9  # every fixture winner reached exactly the chart's points target
        assert race["chart"]["5"] == 38


class TestLineup:
    def test_matrix_covers_every_scheduled_week(self, doc):
        lineup = doc["lineup"]
        assert lineup["weeks"] == [1, 2, 3, 4, 5]
        ann = next(r for r in lineup["rows"] if r["name"] == "Ann Fixture")
        assert [len(c) for c in ann["cells"]] == [1, 2, 1, 0, 0]
        ed = next(r for r in lineup["rows"] if r["name"] == "Ed Mock")
        assert [len(c) for c in ed["cells"]] == [1, 0, 1, 0, 0]


class TestHistoryAndCareer:
    def test_prior_season_is_linked_by_team_name(self, doc):
        sessions = doc["history"]
        assert [s["session_name"] for s in sessions] == ["Spring 2026", "Fall 2026"]
        spring = sessions[0]
        assert (spring["wins"], spring["losses"]) == (1, 1)
        assert spring["points_for"] == 129.0 and spring["is_current"] is False
        ann = next(p for p in spring["players"] if p["name"] == "Ann Fixture")
        assert ann["games"] == 1 and ann["skill_level_end"] == 4

    def test_career_rows_for_rostered_players(self, doc):
        career = doc["career"]
        assert len(career) == 1
        assert career[0]["name"] == "Ann Fixture" and career[0]["format"] == "nine"
        assert career[0]["matches_won"] == 45 and career[0]["win_pct"] == round(45 / 85, 4)

    def test_history_carries_no_team_rank(self, doc):
        """PlayerTeamHistory.rank is a per-player MVP rank; it must never be
        presented as the team's standing (observed live: 'rank 24' in a
        ten-team division)."""
        assert all("final_rank" not in s for s in doc["history"])
