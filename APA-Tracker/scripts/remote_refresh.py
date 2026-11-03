#!/usr/bin/env python3
"""Unattended remote refresh: headless APA login -> live refresh -> verified
Coach Cockpit -> stable publish directory.

Why this exists
    scripts/run_game_night.py already does the whole safe refresh (live
    division-wide acquisition, verification, one independently verified
    Coach Cockpit per team the account plays on, promotion). It expects an
    APA_ACCESS_TOKEN that a human obtained by logging in through a visible
    Chromium window. A cloud session has no screen and no human at the
    keyboard, so this script adds the one missing step: a bounded,
    headless login that reads APA_USERNAME / APA_PASSWORD from the
    environment, observes the token the APA site itself attaches to its
    GraphQL calls, and hands it to the launcher in memory only.

    Everything else is delegated. This module owns no scraping, analytics,
    rendering, or verification logic.

What it never does
    - never writes the password or token to disk, logs, or stdout
    - never reads credentials from apa_config.yaml or a .env file
    - never screenshots, records video/HAR, or traces the browser
    - never opens a browser window on anyone's desktop

Usage
    python scripts/remote_refresh.py                 # all current teams
    python scripts/remote_refresh.py --our-team-id 13082948
    python scripts/remote_refresh.py --resume        # continue an interrupted refresh
    python scripts/remote_refresh.py --backfill      # career history first, then refresh
    python scripts/remote_refresh.py --fresh         # archive the database and rebuild it

Token expiry
    The APA access token is short-lived and a career backfill can outlast
    it. When a step fails on an expired token, this logs in again (bounded by
    --max-logins) and resumes that step, so already-captured scoresheets are
    never refetched.

Environment
    APA_ACCESS_TOKEN   optional; if set, used as-is and no login happens
    APA_USERNAME       APA Member Services login email
    APA_PASSWORD       APA Member Services password

Output
    exports/remote/<team_id>/dashboard.html   Coach Cockpit, one self-contained page per team
    exports/remote/<team_id>/analytics.html   Team Analytics, one self-contained page per team
    exports/remote/manifest.json              team names, build time, source hash

    Each dashboard.html is a single file with no external links, so it can be
    published as-is (for example as a private claude.ai artifact).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.graphql_scraper import AccessTokenExpired, AccessTokenMissing
from scripts import backfill_career_history as career
from scripts import build_team_analytics as analytics_builder
from scripts import run_game_night as launcher

logger = logging.getLogger("remote_refresh")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PUBLISH_DIR = PROJECT_ROOT / "exports" / "remote"

LEAGUE_URL = "https://league.poolplayers.com"
LOGIN_URL = f"{LEAGUE_URL}/login"
GRAPHQL_HOST = "gql.poolplayers.com"
LOGIN_BUTTON_NAME = "Log In"
# After login, accounts.poolplayers.com/authorize shows an interstitial headed
# "Continue to Member Services" with the signed-in member and one button whose
# accessible name is exactly "Continue". The heading is not clickable; the
# button is what advances to league.poolplayers.com.
CONTINUE_BUTTON_NAME = "Continue"

DEFAULT_LOGIN_TIMEOUT_S = 180.0
FORM_TIMEOUT_MS = 30_000
DEFAULT_MAX_LOGINS = 4
CONFIG_PATH = PROJECT_ROOT / "apa_config.yaml"

# A current desktop Chrome user agent. The headless shell otherwise announces
# itself as HeadlessChrome, which some login front-ends treat differently.
# This is the account owner logging in to their own account; nothing is
# impersonated.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

EXIT_OK = 0
EXIT_NO_CREDENTIALS = 3
EXIT_LOGIN_FAILED = 5


class RemoteRefreshError(RuntimeError):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


# --- token --------------------------------------------------------------------

def acquire_token(
    username: str,
    password: str,
    *,
    timeout_s: float = DEFAULT_LOGIN_TIMEOUT_S,
    sync_playwright: Optional[Callable] = None,
) -> Optional[str]:
    """Log in headlessly and return the authorization header the APA app
    attaches to its own GraphQL calls, or None if none was observed in time.

    Success is defined exactly as in tools/run_ultimate_coach_browser.py: a
    real request to gql.poolplayers.com carried a real `authorization`
    header. URL changes, titles, and timers alone never count.
    """
    if sync_playwright is None:
        try:
            from playwright.sync_api import sync_playwright as _sp
        except ImportError:
            raise SystemExit(
                "Playwright is not installed. Run:\n"
                "  pip install -r requirements-dev.txt\n"
                "  python -m playwright install chromium"
            )
        sync_playwright = _sp

    token_holder: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()

            def on_response(response) -> None:
                if GRAPHQL_HOST not in response.url:
                    return
                auth = response.request.headers.get("authorization")
                if auth:
                    token_holder["token"] = auth

            context.on("response", on_response)

            logger.info("Opening the APA login page...")
            page.goto(LOGIN_URL)
            # league.poolplayers.com/login redirects to accounts.poolplayers.com,
            # whose form has #email and #password inputs and one "Log In"
            # button. That button carries no type attribute (so
            # button[type=submit] matches nothing) and stays disabled until
            # both fields are filled, so fill first, then click it by role.
            page.wait_for_selector("#email", timeout=FORM_TIMEOUT_MS)
            page.fill("#email", username)
            page.fill("#password", password)
            page.get_by_role("button", name=LOGIN_BUTTON_NAME).click(timeout=FORM_TIMEOUT_MS)
            logger.info("Credentials submitted; waiting for Member Services...")

            deadline = time.monotonic() + timeout_s
            continue_was_visible = False
            while time.monotonic() < deadline and not token_holder.get("token"):
                page.wait_for_timeout(500)
                if token_holder.get("token"):
                    break
                try:
                    control = page.get_by_role("button", name=CONTINUE_BUTTON_NAME, exact=True)
                    visible = bool(control.count() and control.first.is_visible())
                    if visible and not continue_was_visible:
                        control.first.click(timeout=2000)
                        logger.info("Clicked '%s'.", CONTINUE_BUTTON_NAME)
                    continue_was_visible = visible
                except Exception:  # noqa: BLE001 - control is optional
                    continue_was_visible = False

            if not token_holder.get("token"):
                where = "unknown"
                try:
                    where = page.url.split("?")[0]
                except Exception:  # noqa: BLE001
                    pass
                logger.error(
                    "No authorized GraphQL request observed within %ds (page ended at %s). "
                    "Either the login was rejected or an extra verification step appeared.",
                    int(timeout_s), where,
                )
                return None
            logger.info("Authenticated; token captured in memory.")
            return token_holder["token"]
        finally:
            browser.close()


def resolve_token(
    env: Optional[dict] = None,
    *,
    login: Callable[..., Optional[str]] = acquire_token,
    timeout_s: float = DEFAULT_LOGIN_TIMEOUT_S,
) -> str:
    """APA_ACCESS_TOKEN if present, else a headless login with
    APA_USERNAME / APA_PASSWORD. Raises RemoteRefreshError otherwise."""
    env = os.environ if env is None else env
    token = (env.get("APA_ACCESS_TOKEN") or "").strip()
    if token:
        logger.info("Using APA_ACCESS_TOKEN from the environment; no login needed.")
        return token

    username = (env.get("APA_USERNAME") or "").strip()
    password = env.get("APA_PASSWORD") or ""
    if not username or not password:
        raise RemoteRefreshError(
            "No APA credentials available. Set APA_USERNAME and APA_PASSWORD "
            "(or a fresh APA_ACCESS_TOKEN) as environment variables -- in a Claude "
            "Code cloud session, add them under the environment's settings. "
            "Nothing is read from apa_config.yaml or .env.",
            EXIT_NO_CREDENTIALS,
        )

    token = login(username, password, timeout_s=timeout_s)
    if not token:
        raise RemoteRefreshError(
            "Headless APA login did not produce an access token.", EXIT_LOGIN_FAILED
        )
    return token


# --- publish directory ---------------------------------------------------------

def stage_publish_dir(
    dashboard: Path,
    publish_dir: Path,
    *,
    our_team_id: Optional[str] = None,
) -> dict:
    """Copy each team's verified dashboard.html into a stable directory.

    `dashboard` is what run_game_night() returned: <run>/html/dashboard.html.
    In multi-team mode <run>/teams/<id>/html/dashboard.html exist alongside a
    hub-manifest.json with team names; in --our-team-id mode the run itself
    is the single team's Cockpit. The previous publish contents are replaced
    wholesale so a stale team never lingers.
    """
    dashboard = dashboard.resolve()
    run_dir = dashboard.parent.parent
    teams_dir = run_dir / "teams"

    entries: list[dict] = []
    if teams_dir.is_dir():
        names: dict[str, str] = {}
        hub_manifest = run_dir / launcher.HUB_MANIFEST_NAME
        if hub_manifest.is_file():
            hub = json.loads(hub_manifest.read_text(encoding="utf-8"))
            for team in hub.get("teams") or []:
                names[str(team.get("team_id") or "")] = str(team.get("team_name") or "")
        for child in sorted(teams_dir.iterdir()):
            page = child / "html" / "dashboard.html"
            if page.is_file():
                entries.append({"team_id": child.name, "team_name": names.get(child.name) or child.name, "source": page})
    else:
        team_id = str(our_team_id or run_dir.name)
        entries.append({"team_id": team_id, "team_name": team_id, "source": dashboard})

    if not entries:
        raise RemoteRefreshError(f"no dashboard.html found under {run_dir}", launcher.EXIT_VERIFY)

    publish_dir = publish_dir.resolve()
    if publish_dir.exists():
        shutil.rmtree(publish_dir)
    publish_dir.mkdir(parents=True)

    manifest_teams = []
    for entry in entries:
        target = publish_dir / entry["team_id"] / "dashboard.html"
        target.parent.mkdir(parents=True)
        shutil.copyfile(entry["source"], target)
        manifest_teams.append(
            {
                "team_id": entry["team_id"],
                "team_name": entry["team_name"],
                "path": target.relative_to(publish_dir).as_posix(),
                "sha256": launcher._sha256(target),
            }
        )

    run_manifest = run_dir / launcher.cockpit_builder.MANIFEST_NAME
    if not run_manifest.is_file():
        run_manifest = run_dir / launcher.HUB_MANIFEST_NAME
    source_manifest = json.loads(run_manifest.read_text(encoding="utf-8")) if run_manifest.is_file() else {}

    manifest = {
        "schema_version": "remote-publish-v1",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "built_at": source_manifest.get("built_at"),
        "database_sha256": source_manifest.get("database_sha256"),
        "source_run": run_dir.name,
        "teams": manifest_teams,
    }
    (publish_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# --- token expiry / re-login -----------------------------------------------------

def is_token_expiry(exc: BaseException) -> bool:
    """Whether a failure means the APA token died mid-run. The production
    builder reports its acquisition failures by exception CLASS NAME only
    (never the payload), so the name is matched in the message too."""
    if isinstance(exc, (AccessTokenExpired, AccessTokenMissing)):
        return True
    text = str(exc)
    return "AccessTokenExpired" in text or "AccessTokenMissing" in text


class _TokenSession:
    """Holds the in-memory token for this process and re-logs-in on demand.

    APA_ACCESS_TOKEN given from the outside is used once and never
    "refreshed": a re-login needs the username/password path, so an
    outside token that expires is a hard stop.
    """

    def __init__(self, resolver: Callable[..., str], timeout_s: float, max_logins: int):
        self._resolver = resolver
        self._timeout_s = timeout_s
        self._max_logins = max(1, int(max_logins))
        self.logins = 0
        self._had_outside_token = bool((os.environ.get("APA_ACCESS_TOKEN") or "").strip())

    def login(self) -> None:
        if self.logins >= self._max_logins:
            raise RemoteRefreshError(
                f"APA token expired again after {self.logins} login(s); giving up "
                f"(--max-logins {self._max_logins}).", EXIT_LOGIN_FAILED,
            )
        if self.logins == 0:
            token = self._resolver(timeout_s=self._timeout_s)
        else:
            if self._had_outside_token:
                raise RemoteRefreshError(
                    "The APA_ACCESS_TOKEN given in the environment expired; set a fresh one "
                    "or provide APA_USERNAME/APA_PASSWORD so the run can log in again.",
                    EXIT_LOGIN_FAILED,
                )
            without_token = {k: v for k, v in os.environ.items() if k != "APA_ACCESS_TOKEN"}
            token = self._resolver(without_token, timeout_s=self._timeout_s)
        os.environ["APA_ACCESS_TOKEN"] = token  # this process only; never persisted
        self.logins += 1

    def close(self) -> None:
        if not self._had_outside_token:
            os.environ.pop("APA_ACCESS_TOKEN", None)

    def run_resumable(self, label: str, step: Callable[[bool], object], *, resume: bool):
        """Run ``step(resume)``; on token expiry log in again and call
        ``step(True)`` so the step continues from its own checkpoints."""
        while True:
            try:
                return step(resume)
            except Exception as exc:  # noqa: BLE001 - classified below, re-raised if not expiry
                if not is_token_expiry(exc):
                    raise
                logger.warning("%s: APA token expired mid-run; logging in again and resuming.", label)
                self.login()
                resume = True


def archive_databases(data_dir: Path = PROJECT_ROOT / "data") -> Optional[Path]:
    """Move the production and staging databases into a timestamped archive
    folder so the next refresh rebuilds from the API. Never deletes."""
    names = ("apa_tracker.db", "apa_tracker_regenerated.db", "apa_tracker_career_staging.db")
    present = [data_dir / n for n in names if (data_dir / n).is_file()]
    if not present:
        return None
    target = data_dir / f"archive-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    target.mkdir(parents=True)
    for path in present:
        shutil.move(str(path), str(target / path.name))
    logger.info("Archived %d database file(s) to %s", len(present), target)
    return target


def add_team_analytics(
    manifest: dict, publish_dir: Path, *,
    analytics_build: Callable[..., tuple[Path, dict]] = analytics_builder.build,
    db_path: Path = launcher.production_builder.LIVE_PRODUCTION_DB,
) -> dict:
    """Build the Team Analytics page for every published team from the
    promoted production database and record it in the manifest. A team whose
    analytics build fails keeps its Cockpit; the failure is recorded, never
    hidden."""
    publish_dir = publish_dir.resolve()
    for team in manifest["teams"]:
        try:
            html_path, _doc = analytics_build(db_path, team["team_id"], publish_dir)
            team["analytics_path"] = html_path.resolve().relative_to(publish_dir).as_posix()
            team["analytics_sha256"] = launcher._sha256(html_path)
        except Exception as exc:  # noqa: BLE001 - category and message only
            team["analytics_error"] = f"{type(exc).__name__}: {exc}"
            logger.error("Team Analytics for %s failed: %s", team["team_name"], team["analytics_error"])
    return manifest


# --- main ----------------------------------------------------------------------

def run(
    *,
    resume: bool = False,
    our_team_id: Optional[str] = None,
    publish_dir: Path = DEFAULT_PUBLISH_DIR,
    login_timeout_s: float = DEFAULT_LOGIN_TIMEOUT_S,
    backfill: bool = False,
    fresh: bool = False,
    max_logins: int = DEFAULT_MAX_LOGINS,
    token_resolver: Callable[..., str] = resolve_token,
    game_night: Callable[..., Path] = launcher.run_game_night,
    career_backfill: Callable[..., dict] = career.run_backfill,
    archive: Callable[[], Optional[Path]] = archive_databases,
    analytics_build: Callable[..., tuple[Path, dict]] = analytics_builder.build,
) -> dict:
    if fresh:
        archive()

    session = _TokenSession(token_resolver, login_timeout_s, max_logins)
    session.login()
    try:
        if backfill:
            logger.info("Career backfill: every historical division this account played in...")
            report = session.run_resumable(
                "career backfill",
                lambda resume_flag: career_backfill(
                    str(CONFIG_PATH), career.DEFAULT_STAGING_DB, resume=resume_flag, promote=True,
                ),
                resume=False,
            )
            totals = (report or {}).get("totals") or {}
            logger.info(
                "Career backfill promoted: %s division(s), %s scored match(es) with scoresheets.",
                (report or {}).get("divisions_discovered"), totals.get("scored_matches_with_scoresheet"),
            )
        dashboard = session.run_resumable(
            "game-night refresh",
            lambda resume_flag: game_night(resume=resume_flag, open_browser=False, our_team_id=our_team_id),
            resume=resume,
        )
    finally:
        session.close()
    manifest = stage_publish_dir(dashboard, publish_dir, our_team_id=our_team_id)
    add_team_analytics(manifest, publish_dir, analytics_build=analytics_build)
    (publish_dir.resolve() / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Published %d team dashboard(s) to %s", len(manifest["teams"]), publish_dir)
    for team in manifest["teams"]:
        logger.info("  %s  %s  %s", team["team_name"], publish_dir / team["path"], publish_dir / team.get("analytics_path", ""))
    return manifest


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted live staging refresh.")
    parser.add_argument("--our-team-id", help="Build only this team instead of every team the account plays on.")
    parser.add_argument("--publish-dir", default=str(DEFAULT_PUBLISH_DIR), help="Where the per-team dashboards land.")
    parser.add_argument(
        "--login-timeout", type=float, default=DEFAULT_LOGIN_TIMEOUT_S,
        help="Seconds to wait after submitting credentials for an authorized GraphQL call.",
    )
    parser.add_argument(
        "--backfill", action="store_true",
        help="First run the career-history backfill (every past division this account played in) "
             "and promote it, then do the normal refresh on top of it.",
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Move the production and staging databases into data/archive-<timestamp>/ first, so "
             "the run rebuilds everything from the API. Nothing is deleted.",
    )
    parser.add_argument(
        "--max-logins", type=int, default=DEFAULT_MAX_LOGINS,
        help="How many times to log in again when the short-lived APA token expires mid-run.",
    )
    args = parser.parse_args(argv)

    try:
        run(
            resume=args.resume,
            our_team_id=args.our_team_id,
            publish_dir=Path(args.publish_dir),
            login_timeout_s=args.login_timeout,
            backfill=args.backfill,
            fresh=args.fresh,
            max_logins=args.max_logins,
        )
    except RemoteRefreshError as exc:
        logger.error("REMOTE REFRESH FAILED: %s", exc)
        return exc.code
    except launcher.GameNightError as exc:
        logger.error("REMOTE REFRESH FAILED: %s", exc)
        return exc.code
    except (launcher.production_builder.BuildError, launcher.cockpit_builder.BuildError) as exc:
        logger.error("REMOTE REFRESH FAILED: %s", exc)
        return exc.code
    except career.CareerBackfillError as exc:
        logger.error("REMOTE REFRESH FAILED (career backfill): %s", exc)
        return launcher.EXIT_VERIFY
    except KeyboardInterrupt:
        logger.error("interrupted")
        return launcher.EXIT_INTERRUPT
    except Exception as exc:  # noqa: BLE001 - report the category and message, never a payload
        logger.error("REMOTE REFRESH FAILED (unexpected %s): %s", type(exc).__name__, exc)
        return 1
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
