"""The Team Analytics page: builder output, embedded document, and a real
headless-Chromium pass (no console errors, no horizontal overflow, the table
toggles work, the filters re-render) in both color schemes."""
from __future__ import annotations

import json

import pytest

from scripts import build_team_analytics as builder
from tests.team_analytics_fixture import OUR_ID, OUR_NAME, build

playwright_sync_api = pytest.importorskip("playwright.sync_api")
sync_playwright = playwright_sync_api.sync_playwright


@pytest.fixture(scope="module")
def page_path(tmp_path_factory):
    root = tmp_path_factory.mktemp("ta-page")
    db = build(root / "fixture.db")
    html_path, doc = builder.build(builder.Path(db), OUR_ID, root / "out")
    return html_path, doc


def test_builder_writes_page_and_document(page_path):
    html_path, doc = page_path
    assert html_path.name == "analytics.html" and html_path.parent.name == OUR_ID
    on_disk = json.loads((html_path.parent / "analytics.json").read_text(encoding="utf-8"))
    assert on_disk["team"]["name"] == OUR_NAME
    html = html_path.read_text(encoding="utf-8")
    assert f"<title>{OUR_NAME} Analytics</title>" in html
    assert 'id="ta-data"' in html
    assert "</script>" not in json.dumps(doc).replace("</", "<\\/")  # the embed escaping holds
    assert "http" not in html.replace("https://fonts.googleapis.com", "").replace("http://www.w3.org/2000/svg", "")


def test_cli_builds_for_each_team(tmp_path):
    db = build(tmp_path / "fixture.db")
    assert builder.main(["--db", db, "--team-id", OUR_ID, "--out", str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / OUR_ID / "analytics.html").is_file()


@pytest.mark.parametrize("scheme,width", [("light", 1200), ("dark", 1200), ("light", 400)])
def test_page_renders_without_errors_and_responds(page_path, scheme, width):
    html_path, _ = page_path
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=scheme)
        page = context.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(html_path.as_uri())
        page.wait_for_timeout(300)

        assert page.locator("h1").inner_text() == OUR_NAME
        assert "2–1" in page.locator("#hero").inner_text()
        assert page.locator("#fig-trajectory svg polyline").count() == 4  # every division team drawn
        assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

        # table twin toggles
        toggle = page.locator("#fig-trajectory .toggle")
        toggle.click()
        assert page.locator("#fig-trajectory table.data").count() == 1
        assert toggle.inner_text() == "Chart"

        # player filter narrows every player-scoped figure
        page.select_option("#f-player", "Ed Mock")
        assert page.locator("#fig-players tbody tr").count() == 1
        assert page.locator("#fig-lineup tbody tr").count() == 1
        page.select_option("#f-session", "Spring 2026")
        assert "Earlier season" in page.locator("#f-note").inner_text()

        assert errors == []
        browser.close()
