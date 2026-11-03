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

Environment
    APA_ACCESS_TOKEN   optional; if set, used as-is and no login happens
    APA_USERNAME       APA Member Services login email
    APA_PASSWORD       APA Member Services password

Output
    exports/remote/<team_id>/dashboard.html   one self-contained page per team
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

from scripts import run_game_night as launcher

logger = logging.getLogger("remote_refresh")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PUBLISH_DIR = PROJECT_ROOT / "exports" / "remote"

LEAGUE_URL = "https://league.poolplayers.com"
LOGIN_URL = f"{LEAGUE_URL}/login"
GRAPHQL_HOST = "gql.poolplayers.com"
CONTINUE_TEXT = "Continue to Member Services"

DEFAULT_LOGIN_TIMEOUT_S = 180.0
FORM_TIMEOUT_MS = 30_000

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
            # whose form has #email and #password inputs and one submit button.
            page.wait_for_selector("#email", timeout=FORM_TIMEOUT_MS)
            page.fill("#email", username)
            page.fill("#password", password)
            page.click("button[type=submit]")
            logger.info("Credentials submitted; waiting for Member Services...")

            deadline = time.monotonic() + timeout_s
            continue_was_visible = False
            while time.monotonic() < deadline and not token_holder.get("token"):
                page.wait_for_timeout(500)
                if token_holder.get("token"):
                    break
                try:
                    control = page.get_by_text(CONTINUE_TEXT, exact=False)
                    visible = bool(control.count() and control.first.is_visible())
                    if visible and not continue_was_visible:
                        control.first.click(timeout=2000)
                        logger.info("Clicked '%s'.", CONTINUE_TEXT)
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


# --- main ----------------------------------------------------------------------

def run(
    *,
    resume: bool = False,
    our_team_id: Optional[str] = None,
    publish_dir: Path = DEFAULT_PUBLISH_DIR,
    login_timeout_s: float = DEFAULT_LOGIN_TIMEOUT_S,
    token_resolver: Callable[..., str] = resolve_token,
    game_night: Callable[..., Path] = launcher.run_game_night,
) -> dict:
    token = token_resolver(timeout_s=login_timeout_s)
    had_token = "APA_ACCESS_TOKEN" in os.environ
    os.environ["APA_ACCESS_TOKEN"] = token  # this process only; never persisted
    try:
        dashboard = game_night(resume=resume, open_browser=False, our_team_id=our_team_id)
    finally:
        if not had_token:
            os.environ.pop("APA_ACCESS_TOKEN", None)
    manifest = stage_publish_dir(dashboard, publish_dir, our_team_id=our_team_id)
    logger.info("Published %d team dashboard(s) to %s", len(manifest["teams"]), publish_dir)
    for team in manifest["teams"]:
        logger.info("  %s  %s", team["team_name"], publish_dir / team["path"])
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
    args = parser.parse_args(argv)

    try:
        run(
            resume=args.resume,
            our_team_id=args.our_team_id,
            publish_dir=Path(args.publish_dir),
            login_timeout_s=args.login_timeout,
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
    except KeyboardInterrupt:
        logger.error("interrupted")
        return launcher.EXIT_INTERRUPT
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
