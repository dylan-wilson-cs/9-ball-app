from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts import remote_refresh as remote
from scripts import run_game_night as launcher


# --- resolve_token -------------------------------------------------------------

def test_env_token_wins_and_login_is_never_called():
    def must_not_login(*args, **kwargs):
        raise AssertionError("login must not run when APA_ACCESS_TOKEN is set")

    token = remote.resolve_token(
        {"APA_ACCESS_TOKEN": " tok-123 ", "APA_USERNAME": "u", "APA_PASSWORD": "p"},
        login=must_not_login,
    )
    assert token == "tok-123"


def test_missing_credentials_fail_closed_with_guidance():
    with pytest.raises(remote.RemoteRefreshError) as excinfo:
        remote.resolve_token({}, login=lambda *a, **k: "never")
    assert excinfo.value.code == remote.EXIT_NO_CREDENTIALS
    message = str(excinfo.value)
    assert "APA_USERNAME" in message and "APA_PASSWORD" in message
    assert "apa_config.yaml" in message


def test_username_password_go_to_login_and_its_token_is_returned():
    seen = {}

    def fake_login(username, password, *, timeout_s):
        seen.update(username=username, password=password, timeout_s=timeout_s)
        return "live-token"

    token = remote.resolve_token(
        {"APA_USERNAME": "me@example.com", "APA_PASSWORD": "s3cret"},
        login=fake_login, timeout_s=42,
    )
    assert token == "live-token"
    assert seen == {"username": "me@example.com", "password": "s3cret", "timeout_s": 42}


def test_login_without_token_is_a_distinct_failure():
    with pytest.raises(remote.RemoteRefreshError) as excinfo:
        remote.resolve_token(
            {"APA_USERNAME": "u", "APA_PASSWORD": "p"}, login=lambda *a, **k: None
        )
    assert excinfo.value.code == remote.EXIT_LOGIN_FAILED


# --- acquire_token with Playwright fully faked ----------------------------------

class _FakeLocator:
    def __init__(self, count=0, visible=True):
        self._count = count
        self._visible = visible
        self.click_calls = 0

    def count(self):
        return self._count

    @property
    def first(self):
        return self

    def is_visible(self):
        return self._visible

    def click(self, timeout=None):
        self.click_calls += 1


class _FakeRequest:
    def __init__(self, headers):
        self.headers = headers


class _FakeResponse:
    def __init__(self, url, headers):
        self.url = url
        self.request = _FakeRequest(headers)


class _FakePage:
    def __init__(self, *, continue_locator=None, on_tick=None):
        self.goto_url = None
        self.filled: dict[str, str] = {}
        self.clicked: list[str] = []
        self.waited_for: list[str] = []
        self.url = "https://accounts.poolplayers.com/login"
        self._continue_locator = continue_locator or _FakeLocator(count=0)
        self._on_tick = on_tick
        self.tick_count = 0

    def goto(self, url):
        self.goto_url = url

    def wait_for_selector(self, selector, timeout=None):
        self.waited_for.append(selector)

    def fill(self, selector, value):
        self.filled[selector] = value

    def get_by_role(self, role, name=None):
        assert (role, name) == ("button", remote.LOGIN_BUTTON_NAME)
        page = self

        class _Clickable:
            def click(self, timeout=None):
                page.clicked.append(f"role=button name={name}")

        return _Clickable()

    def wait_for_timeout(self, ms):
        self.tick_count += 1
        if self._on_tick:
            self._on_tick(self.tick_count)

    def get_by_text(self, text, exact=False):
        assert text == remote.CONTINUE_TEXT
        return self._continue_locator


class _FakeContext:
    def __init__(self, page):
        self._page = page
        self.handlers: dict[str, object] = {}
        self.user_agent = None

    def on(self, event, handler):
        self.handlers[event] = handler

    def new_page(self):
        return self._page


class _FakeBrowser:
    def __init__(self, context):
        self._context = context
        self.closed = False
        self.launch_kwargs = None

    def new_context(self, **kwargs):
        self._context.user_agent = kwargs.get("user_agent")
        return self._context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self._browser = browser

    def launch(self, **kwargs):
        self._browser.launch_kwargs = kwargs
        return self._browser


class _FakePlaywright:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _wire(page):
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    return context, browser, (lambda: _FakePlaywright(browser))


def test_acquire_token_fills_form_submits_and_captures_authorization_header():
    holder = {}

    def on_tick(n):
        if n == 3:  # the app's first authorized GraphQL call, a moment after login
            holder["ctx"].handlers["response"](
                _FakeResponse("https://gql.poolplayers.com/graphql", {"authorization": "eyJ.real.token"})
            )

    page = _FakePage(on_tick=on_tick)
    context, browser, factory = _wire(page)
    holder["ctx"] = context

    token = remote.acquire_token("me@example.com", "s3cret", timeout_s=30, sync_playwright=factory)

    assert token == "eyJ.real.token"
    assert page.goto_url == remote.LOGIN_URL
    assert page.waited_for == ["#email"]
    assert page.filled == {"#email": "me@example.com", "#password": "s3cret"}
    assert page.clicked == ["role=button name=Log In"]
    assert browser.launch_kwargs == {"headless": True}
    assert "Headless" not in (context.user_agent or "Headless")
    assert browser.closed is True


def test_acquire_token_ignores_other_hosts_and_unauthenticated_calls():
    holder = {}

    def on_tick(n):
        handler = holder["ctx"].handlers["response"]
        if n == 1:
            handler(_FakeResponse("https://accounts.poolplayers.com/api", {"authorization": "not-gql"}))
        if n == 2:
            handler(_FakeResponse("https://gql.poolplayers.com/graphql", {}))
        if n == 4:
            handler(_FakeResponse("https://gql.poolplayers.com/graphql", {"authorization": "yes"}))

    page = _FakePage(on_tick=on_tick)
    context, browser, factory = _wire(page)
    holder["ctx"] = context

    assert remote.acquire_token("u", "p", timeout_s=30, sync_playwright=factory) == "yes"
    assert page.tick_count == 4


def test_acquire_token_clicks_continue_once_while_visible():
    locator = _FakeLocator(count=1, visible=True)
    holder = {}

    def on_tick(n):
        if n == 5:
            holder["ctx"].handlers["response"](
                _FakeResponse("https://gql.poolplayers.com/graphql", {"authorization": "tok"})
            )

    page = _FakePage(continue_locator=locator, on_tick=on_tick)
    context, browser, factory = _wire(page)
    holder["ctx"] = context

    assert remote.acquire_token("u", "p", timeout_s=30, sync_playwright=factory) == "tok"
    assert locator.click_calls == 1


def test_acquire_token_returns_none_on_timeout_and_still_closes_browser(monkeypatch):
    clock = {"t": 0.0}
    monkeypatch.setattr(remote.time, "monotonic", lambda: clock["t"])

    def on_tick(n):
        clock["t"] += 1.0

    page = _FakePage(on_tick=on_tick)
    context, browser, factory = _wire(page)

    assert remote.acquire_token("u", "p", timeout_s=3, sync_playwright=factory) is None
    assert browser.closed is True


# --- stage_publish_dir ---------------------------------------------------------

def _hub_run(run_dir: Path, teams: dict[str, str]) -> Path:
    for team_id in teams:
        page = run_dir / "teams" / team_id / "html" / "dashboard.html"
        page.parent.mkdir(parents=True)
        page.write_text(f"<html>{team_id}</html>", encoding="utf-8")
    hub = run_dir / "html" / "dashboard.html"
    hub.parent.mkdir(parents=True)
    hub.write_text("<html>hub</html>", encoding="utf-8")
    (run_dir / launcher.HUB_MANIFEST_NAME).write_text(json.dumps({
        "built_at": "2026-11-03T00:00:00+00:00",
        "database_sha256": "abc123",
        "teams": [{"team_id": tid, "team_name": name} for tid, name in teams.items()],
    }), encoding="utf-8")
    return hub


def test_stage_hub_run_copies_every_team_and_replaces_previous_publish(tmp_path):
    hub = _hub_run(tmp_path / "game-night-1", {"111": "Chalk It Up", "222": "Rack Attack"})
    publish = tmp_path / "publish"
    stale = publish / "999" / "dashboard.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("old", encoding="utf-8")

    manifest = remote.stage_publish_dir(hub, publish)

    assert (publish / "111" / "dashboard.html").read_text(encoding="utf-8") == "<html>111</html>"
    assert (publish / "222" / "dashboard.html").read_text(encoding="utf-8") == "<html>222</html>"
    assert not stale.exists()
    assert [t["team_name"] for t in manifest["teams"]] == ["Chalk It Up", "Rack Attack"]
    assert manifest["database_sha256"] == "abc123"
    assert manifest["built_at"] == "2026-11-03T00:00:00+00:00"
    on_disk = json.loads((publish / "manifest.json").read_text(encoding="utf-8"))
    assert on_disk["teams"][0]["path"] == "111/dashboard.html"
    assert on_disk["teams"][0]["sha256"] == launcher._sha256(publish / "111" / "dashboard.html")


def test_stage_single_team_run_uses_the_given_team_id(tmp_path):
    run_dir = tmp_path / "game-night-2"
    page = run_dir / "html" / "dashboard.html"
    page.parent.mkdir(parents=True)
    page.write_text("<html>solo</html>", encoding="utf-8")
    (run_dir / launcher.cockpit_builder.MANIFEST_NAME).write_text(
        json.dumps({"built_at": "b", "database_sha256": "d"}), encoding="utf-8"
    )

    manifest = remote.stage_publish_dir(page, tmp_path / "publish", our_team_id="13082948")

    assert manifest["teams"] == [{
        "team_id": "13082948", "team_name": "13082948",
        "path": "13082948/dashboard.html",
        "sha256": launcher._sha256(tmp_path / "publish" / "13082948" / "dashboard.html"),
    }]
    assert manifest["database_sha256"] == "d"


def test_stage_fails_closed_when_no_dashboard_exists(tmp_path):
    run_dir = tmp_path / "empty"
    (run_dir / "teams").mkdir(parents=True)
    (run_dir / "html").mkdir()
    with pytest.raises(remote.RemoteRefreshError):
        remote.stage_publish_dir(run_dir / "html" / "dashboard.html", tmp_path / "publish")


# --- run() wiring --------------------------------------------------------------

def test_run_sets_token_only_for_the_launcher_and_removes_it_after(tmp_path, monkeypatch):
    monkeypatch.delenv("APA_ACCESS_TOKEN", raising=False)
    observed = {}

    def fake_game_night(*, resume, open_browser, our_team_id):
        observed.update(
            token=os.environ.get("APA_ACCESS_TOKEN"), resume=resume,
            open_browser=open_browser, our_team_id=our_team_id,
        )
        return _hub_run(tmp_path / "run", {"1": "One"})

    manifest = remote.run(
        resume=True, our_team_id=None, publish_dir=tmp_path / "pub",
        token_resolver=lambda **kw: "in-memory-token", game_night=fake_game_night,
    )

    assert observed == {"token": "in-memory-token", "resume": True, "open_browser": False, "our_team_id": None}
    assert "APA_ACCESS_TOKEN" not in os.environ
    assert manifest["teams"][0]["team_name"] == "One"
    assert (tmp_path / "pub" / "1" / "dashboard.html").is_file()


def test_main_maps_missing_credentials_to_its_exit_code(monkeypatch):
    for var in ("APA_ACCESS_TOKEN", "APA_USERNAME", "APA_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(remote.launcher, "run_game_night", lambda **kw: (_ for _ in ()).throw(
        AssertionError("launcher must not run without credentials")
    ))
    assert remote.main([]) == remote.EXIT_NO_CREDENTIALS
