"""Team Analytics page: one self-contained HTML file per team, rendered from
analytics.team_analytics.build_team_analytics()'s document.

The document is embedded verbatim as JSON and every chart is drawn client-side
as inline SVG from it, so the page has no external script and nothing in the
markup is hand-typed data. Charts follow one method: thin marks, hairline
grid, one emphasis hue for our team against a quiet gray for the division, a
legend wherever two series share a plot, a table view twin behind every chart,
and a tooltip that never gates a value.
"""
from __future__ import annotations

import json
from html import escape
from typing import Any

PAGE = r"""<title>__TITLE__</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&display=swap">
<style>
/* Layout: a scoreboard header, a one-row filter bar, then stacked sections of
   figure cards. Display face only on headings and the hero record; every
   number and chart label stays in the system sans. */
:root {
  --bg: #f4f3ee;            /* page plane: warm chalk */
  --surface: #fcfcfb;       /* chart surface (validated) */
  --ink: #0b0b0b;
  --ink-2: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --axis: #c3c2b7;
  --felt: #1e5c47;          /* table felt: the accent for chrome, not for data */
  --felt-ink: #ffffff;
  --us: #2a78d6;            /* categorical slot 1: our team */
  --them: #eb6834;          /* slot 2: opponent / losses */
  --third: #1baf7a;         /* slot 3 */
  --other: #b8b6ae;         /* de-emphasis: the rest of the division */
  --us-wash: rgba(42,120,214,0.10);
  --pos: #2a78d6;           /* diverging pole: ahead */
  --neg: #e34948;           /* diverging pole: behind */
  --mid: #f0efec;
  --good: #0ca30c; --warn: #fab219; --bad: #d03b3b;
  --border: rgba(11,11,11,0.10);
  --display: "Barlow Condensed", "Arial Narrow", system-ui, sans-serif;
  --sans: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --felt: #17493a; --felt-ink: #f0efec;
    --us: #3987e5; --them: #d95926; --third: #199e70; --other: #4a4a47; --us-wash: rgba(57,135,229,0.14);
    --pos: #3987e5; --neg: #e66767; --mid: #383835; --border: rgba(255,255,255,0.10);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #0d0d0d; --surface: #1a1a19; --ink: #f0efec; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --felt: #17493a; --felt-ink: #f0efec;
  --us: #3987e5; --them: #d95926; --third: #199e70; --other: #4a4a47; --us-wash: rgba(57,135,229,0.14);
  --pos: #3987e5; --neg: #e66767; --mid: #383835; --border: rgba(255,255,255,0.10);
  color-scheme: dark;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 var(--sans); }
body::before { content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 10; background: var(--felt); }
.wrap { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 0 48px; max-width: 1180px; margin: 0 auto; }
header.board { background: var(--felt); color: var(--felt-ink); }
header.board .wrap { padding-block: 22px 48px; display: grid; gap: 14px; }
.eyebrow { font: 600 12px/1 var(--sans); letter-spacing: 0.12em; text-transform: uppercase; opacity: 0.8; }
h1 { font: 700 clamp(34px, 6vw, 56px)/0.95 var(--display); margin: 0; text-wrap: balance; letter-spacing: 0.005em; }
.hero-row { display: flex; gap: 28px; flex-wrap: wrap; align-items: flex-end; }
.hero { font: 600 clamp(48px, 9vw, 84px)/0.9 var(--display); letter-spacing: 0.01em; }
.hero small { display: block; font: 600 12px/1.3 var(--sans); letter-spacing: 0.1em; text-transform: uppercase; opacity: 0.8; margin-top: 8px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: -26px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 12px 14px; display: grid; gap: 4px; min-width: 0; }
.tile .label { color: var(--ink-2); font-size: 12.5px; }
.tile .value { font: 600 28px/1.05 var(--sans); }
.tile .delta { font-size: 12.5px; color: var(--ink-2); }
.tile .delta.up { color: var(--good); }
.filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin: 22px 0 8px; font-size: 13.5px; color: var(--ink-2); }
.filters label { display: inline-flex; gap: 6px; align-items: center; }
.filters select { font: inherit; padding: 6px 8px; border: 1px solid var(--axis); border-radius: 4px; background: var(--surface); color: var(--ink); }
h2 { font: 600 26px/1.05 var(--display); margin: 32px 0 6px; letter-spacing: 0.01em; text-wrap: balance; }
h2 + p.lede { margin: 0 0 12px; color: var(--ink-2); max-width: 65ch; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
figure.card { margin: 0; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 14px 16px 10px; min-width: 0; }
figure.card figcaption { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; margin-bottom: 8px; }
figure.card figcaption b { font-weight: 600; }
figure.card figcaption span { color: var(--muted); font-size: 12.5px; }
.toggle { font: inherit; font-size: 12.5px; color: var(--ink-2); background: none; border: 1px solid var(--axis); border-radius: 4px; padding: 3px 8px; cursor: pointer; }
.toggle:focus-visible, select:focus-visible, button:focus-visible { outline: 2px solid var(--us); outline-offset: 2px; }
.plot { position: relative; width: 100%; }
.plot svg { display: block; width: 100%; height: auto; overflow: visible; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--ink-2); margin: 6px 0 2px; }
.legend i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.legend i.rect { height: 10px; width: 10px; border-radius: 2px; }
.tip { position: absolute; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: 4px; padding: 6px 9px; font-size: 12.5px; box-shadow: 0 2px 8px rgba(0,0,0,0.12); min-width: 120px; z-index: 3; display: none; }
.tip .row { display: flex; justify-content: space-between; gap: 12px; }
.tip .row b { font-weight: 600; }
.tip .row i { display: inline-block; width: 10px; height: 3px; border-radius: 2px; vertical-align: middle; margin-right: 6px; }
.tip .head { color: var(--muted); margin-bottom: 3px; }
table.data { border-collapse: collapse; width: 100%; font-size: 13px; }
table.data th, table.data td { padding: 5px 8px; border-bottom: 1px solid var(--grid); text-align: left; white-space: nowrap; }
table.data td.num, table.data th.num { text-align: right; font-variant-numeric: tabular-nums; }
.scroll { overflow-x: auto; }
.chip { display: inline-block; min-width: 26px; text-align: center; padding: 2px 6px; border-radius: 4px; font-size: 12px; font-weight: 600; border: 1px solid var(--border); }
.chip.W { background: var(--us); color: #fff; border-color: transparent; }
.chip.L { background: var(--them); color: #fff; border-color: transparent; }
.chip.T { background: var(--other); color: var(--ink); }
.chip.pending { color: var(--ink-2); }
.chip.none { color: var(--muted); border-style: dashed; }
.note { color: var(--muted); font-size: 12.5px; margin: 6px 0 0; }
.spark { vertical-align: middle; }
.bar-track { height: 8px; background: var(--mid); border-radius: 4px; overflow: hidden; min-width: 90px; }
.bar-track i { display: block; height: 100%; background: var(--us); border-radius: 0 4px 4px 0; }
.empty { color: var(--muted); padding: 10px 0; }
@media (max-width: 600px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
@media (prefers-reduced-motion: no-preference) { .tile, figure.card { transition: border-color 160ms; } }
</style>

<header class="board"><div class="wrap">
  <div class="eyebrow" id="eyebrow"></div>
  <h1 id="title"></h1>
  <div class="hero-row">
    <div class="hero" id="hero"></div>
    <div id="hero-aside" style="font-size:14px; opacity:0.9; max-width:48ch; padding-bottom:10px"></div>
  </div>
</div></header>

<div class="wrap">
  <div class="kpis" id="kpis"></div>

  <div class="filters" id="filters">
    <label>Season <select id="f-session"></select></label>
    <label>Player <select id="f-player"><option value="">All players</option></select></label>
    <span id="f-note"></span>
  </div>

  <h2>Points race</h2>
  <p class="lede">Cumulative team points by week for every team in the division, from the scored matches themselves. Standings on the APA site update per refresh; this follows the schedule.</p>
  <figure class="card" id="fig-trajectory"></figure>

  <h2>Week by week</h2>
  <p class="lede">Each team match: result, team score, and how many of our five boards we took. A played week APA has not posted yet is marked pending.</p>
  <figure class="card" id="fig-weeks"></figure>

  <h2>Players</h2>
  <p class="lede">Every scoresheet line a player shot for this team, this season. Skill level is tracked for this format only; two-team players have a separate history in their other format.</p>
  <figure class="card" id="fig-players"></figure>

  <div class="grid-2">
    <figure class="card" id="fig-margins"></figure>
    <figure class="card" id="fig-delta"></figure>
  </div>

  <h2>Lineup</h2>
  <p class="lede">Who shot each week. Two chips in one week means that player shot two boards.</p>
  <figure class="card" id="fig-lineup"></figure>

  <h2>Race chart</h2>
  <p class="lede" id="race-lede"></p>
  <figure class="card" id="fig-race"></figure>

  <h2>Seasons</h2>
  <p class="lede">Every season this team name has played, as far back as the captured history goes. Earlier seasons appear once the career backfill has run.</p>
  <figure class="card" id="fig-history"></figure>

  <h2>Lifetime</h2>
  <p class="lede">APA's own lifetime figures for rostered players, per format, where the account can see them.</p>
  <figure class="card" id="fig-career"></figure>

  <p class="note" id="footer"></p>
</div>

<script type="application/json" id="ta-data">__DATA__</script>
<script>
(function () {
  "use strict";
  var DOC = JSON.parse(document.getElementById("ta-data").textContent);
  var css = getComputedStyle(document.documentElement);
  function tok(name) { return css.getPropertyValue(name).trim(); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return node;
  }
  var NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    var node = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") node.textContent = attrs[k]; else node.setAttribute(k, attrs[k]); });
    return node;
  }
  function fmtPct(v) { return v === null || v === undefined ? "–" : Math.round(v * 100) + "%"; }
  function fmtNum(v, d) { return v === null || v === undefined ? "–" : (d ? Number(v).toFixed(d) : String(Math.round(v * 10) / 10)); }
  function shortDate(iso) { if (!iso) return ""; var d = new Date(iso); if (isNaN(d)) return String(iso).slice(0, 10); return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  function fmtLabel(g) { return g === "eight" ? "8-Ball" : g === "nine" ? "9-Ball" : ""; }
  function niceTicks(max, n) {
    if (!(max > 0)) return [0, 1];
    var raw = max / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; }).find(function (s) { return s >= raw; }) || mag * 10;
    var ticks = []; for (var v = 0; v <= max + step * 0.0001; v += step) ticks.push(Math.round(v * 100) / 100);
    if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
    return ticks;
  }

  // ---- figure scaffolding: caption, chart/table toggle, tooltip --------------
  function figure(container, title, sub, drawChart, drawTable) {
    container.innerHTML = "";
    var cap = el("figcaption", null, [el("b", { text: title }), el("span", { text: sub || "" })]);
    var toggle = el("button", { class: "toggle", type: "button", "aria-pressed": "false", text: "Table" });
    cap.appendChild(toggle);
    container.appendChild(cap);
    var plot = el("div", { class: "plot" });
    var tableWrap = el("div", { class: "scroll" });
    tableWrap.hidden = true;
    container.appendChild(plot); container.appendChild(tableWrap);
    var drawn = false;
    try { drawChart(plot); } catch (e) { plot.appendChild(el("p", { class: "empty", text: "Chart unavailable: " + e.message })); }
    toggle.addEventListener("click", function () {
      var showTable = tableWrap.hidden;
      if (showTable && !drawn) { tableWrap.appendChild(drawTable()); drawn = true; }
      tableWrap.hidden = !showTable; plot.hidden = showTable;
      toggle.textContent = showTable ? "Chart" : "Table"; toggle.setAttribute("aria-pressed", String(showTable));
    });
    return plot;
  }
  function tooltip(plot) {
    var tip = el("div", { class: "tip", role: "status" });
    plot.appendChild(tip);
    return {
      show: function (x, y, head, rows) {
        tip.innerHTML = "";
        if (head) tip.appendChild(el("div", { class: "head", text: head }));
        rows.forEach(function (r) {
          var row = el("div", { class: "row" });
          var left = el("span"); if (r.color) left.appendChild(el("i", { style: "background:" + r.color })); left.appendChild(document.createTextNode(r.label));
          row.appendChild(left); row.appendChild(el("b", { text: r.value })); tip.appendChild(row);
        });
        tip.style.display = "block";
        var w = plot.clientWidth, tw = tip.offsetWidth;
        tip.style.left = Math.max(0, Math.min(w - tw, x + 12)) + "px";
        tip.style.top = Math.max(0, y - 10) + "px";
      },
      hide: function () { tip.style.display = "none"; }
    };
  }
  function table(cols, rows) {
    var t = el("table", { class: "data" });
    var thead = el("thead"), tr = el("tr");
    cols.forEach(function (c) { tr.appendChild(el("th", { class: c.num ? "num" : "", text: c.label })); });
    thead.appendChild(tr); t.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (r) { var row = el("tr"); cols.forEach(function (c) { row.appendChild(el("td", { class: c.num ? "num" : "", text: r[c.key] === null || r[c.key] === undefined ? "–" : String(r[c.key]) })); }); tbody.appendChild(row); });
    t.appendChild(tbody); return t;
  }
  function legend(items, shape) {
    var l = el("div", { class: "legend" });
    items.forEach(function (it) { var s = el("span"); s.appendChild(el("i", { class: shape === "rect" ? "rect" : "", style: "background:" + it.color })); s.appendChild(document.createTextNode(it.label)); l.appendChild(s); });
    return l;
  }
  function sparkline(values, w, h, color) {
    var svg = svgEl("svg", { viewBox: "0 0 " + w + " " + h, width: w, height: h, class: "spark", role: "img" });
    if (!values.length) return svg;
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    if (min === max) { min -= 1; max += 1; }
    var pts = values.map(function (v, i) { return [(values.length === 1 ? w / 2 : 3 + i * (w - 6) / (values.length - 1)), h - 3 - (v - min) / (max - min) * (h - 6)]; });
    svg.appendChild(svgEl("polyline", { points: pts.map(function (p) { return p.join(","); }).join(" "), fill: "none", stroke: color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    var last = pts[pts.length - 1];
    svg.appendChild(svgEl("circle", { cx: last[0], cy: last[1], r: 3.5, fill: color, stroke: tok("--surface"), "stroke-width": 2 }));
    return svg;
  }

  // ---- state & filters ------------------------------------------------------------
  var state = { session: DOC.team.session_name, player: "" };
  var sessionSel = document.getElementById("f-session"), playerSel = document.getElementById("f-player");
  DOC.history.slice().reverse().forEach(function (s) {
    sessionSel.appendChild(el("option", { value: s.session_name || "", text: (s.session_name || "Season") + (s.is_current ? " (current)" : "") }));
  });
  sessionSel.value = state.session || "";
  DOC.players.forEach(function (p) { playerSel.appendChild(el("option", { value: p.name, text: p.name })); });
  sessionSel.addEventListener("change", function () { state.session = sessionSel.value; renderAll(); });
  playerSel.addEventListener("change", function () { state.player = playerSel.value; renderAll(); });

  function currentPlayers() { return DOC.players.filter(function (p) { return !state.player || p.name === state.player; }); }
  function isCurrentSeason() { return state.session === DOC.team.session_name; }

  // ---- header & KPIs ---------------------------------------------------------------
  function renderHeader() {
    var s = DOC.season, r = s.record;
    document.getElementById("eyebrow").textContent = [fmtLabel(DOC.team.game), DOC.team.session_name, DOC.team.division_id ? "Division " + DOC.team.division_id : ""].filter(Boolean).join("  ·  ");
    document.getElementById("title").textContent = DOC.team.name;
    var hero = document.getElementById("hero");
    hero.textContent = r.wins + "–" + r.losses + (r.ties ? "–" + r.ties : "");
    hero.appendChild(el("small", { text: "team record, " + r.played + " of " + r.scheduled + " weeks played" }));
    var aside = document.getElementById("hero-aside");
    var standing = s.standing ? ("Standing " + s.standing.rank + " of " + s.standing.teams + " with " + fmtNum(s.standing.points) + " points. ") : "";
    aside.textContent = standing + (r.pending ? r.pending + " played week" + (r.pending > 1 ? "s" : "") + " awaiting APA's scoresheet." : "");
    var kpis = document.getElementById("kpis"); kpis.innerHTML = "";
    var lines = DOC.players.reduce(function (acc, p) { return acc.concat(p.lines); }, []);
    var boardsWon = lines.filter(function (l) { return l.result === "W"; }).length;
    var tiles = [
      { label: "Points for", value: fmtNum(s.points.for), delta: "against " + fmtNum(s.points.against) },
      { label: "Boards won", value: boardsWon + " / " + lines.length, delta: fmtPct(lines.length ? boardsWon / lines.length : null) + " of individual matches" },
      { label: "Home", value: s.home_away.home.wins + "–" + (s.home_away.home.played - s.home_away.home.wins), delta: "team matches at home" },
      { label: "Away", value: s.home_away.away.wins + "–" + (s.home_away.away.played - s.home_away.away.wins), delta: "team matches away" },
    ];
    var ob = DOC.players.reduce(function (a, p) { return a + p.on_break; }, 0), br = DOC.players.reduce(function (a, p) { return a + p.break_and_run; }, 0);
    tiles.push({ label: DOC.team.game === "eight" ? "8 on the break" : "9 on the snap", value: String(ob), delta: br + " break and run" + (br === 1 ? "" : "s") });
    tiles.forEach(function (t) { kpis.appendChild(el("div", { class: "tile" }, [el("div", { class: "label", text: t.label }), el("div", { class: "value", text: t.value }), el("div", { class: "delta", text: t.delta })])); });
  }

  // ---- points race: emphasis line chart ----------------------------------------
  function renderTrajectory() {
    var fig = document.getElementById("fig-trajectory"), t = DOC.trajectory;
    var teams = t.teams, weeks = t.weeks;
    var sub = teams.length ? teams.length + " teams, " + weeks.length + " scored week" + (weeks.length === 1 ? "" : "s") : "";
    figure(fig, "Cumulative team points", sub, function (plot) {
      if (!weeks.length) { plot.appendChild(el("p", { class: "empty", text: "No scored matches yet." })); return; }
      // Draw at roughly the rendered width so axis text stays legible on a phone.
      var narrow = plot.clientWidth > 0 && plot.clientWidth < 560;
      var W = narrow ? Math.max(340, plot.clientWidth) : 760, H = narrow ? 260 : 300, m = { t: 14, r: narrow ? 16 : 150, b: 34, l: 44 };
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Cumulative team points by week" });
      var max = Math.max.apply(null, teams.map(function (s) { return Math.max.apply(null, s.cumulative); }));
      var ticks = niceTicks(max, 5), top = ticks[ticks.length - 1];
      var x = function (i) { return m.l + (weeks.length === 1 ? (W - m.l - m.r) / 2 : i * (W - m.l - m.r) / (weeks.length - 1)); };
      var y = function (v) { return m.t + (H - m.t - m.b) * (1 - v / top); };
      ticks.forEach(function (tv) {
        svg.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y(tv), y2: y(tv), stroke: tok("--grid"), "stroke-width": 1 }));
        svg.appendChild(svgEl("text", { x: m.l - 8, y: y(tv) + 4, "text-anchor": "end", "font-size": 11, fill: tok("--muted"), "font-variant-numeric": "tabular-nums", text: String(tv) }));
      });
      weeks.forEach(function (w, i) { svg.appendChild(svgEl("text", { x: x(i), y: H - 12, "text-anchor": "middle", "font-size": 11, fill: tok("--muted"), text: "Wk " + w })); });
      svg.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y(0), y2: y(0), stroke: tok("--axis"), "stroke-width": 1 }));
      var ordered = teams.filter(function (s) { return !s.is_us; }).concat(teams.filter(function (s) { return s.is_us; }));
      var leader = teams[0], labelled = [];
      ordered.forEach(function (s) {
        var color = s.is_us ? tok("--us") : tok("--other");
        var pts = s.cumulative.map(function (v, i) { return x(i) + "," + y(v); }).join(" ");
        svg.appendChild(svgEl("polyline", { points: pts, fill: "none", stroke: color, "stroke-width": s.is_us ? 2.5 : 1.5, "stroke-linejoin": "round", "stroke-linecap": "round" }));
        var last = s.cumulative[s.cumulative.length - 1], lx = x(weeks.length - 1), ly = y(last);
        if (s.is_us) {
          svg.appendChild(svgEl("circle", { cx: lx, cy: ly, r: 4.5, fill: color, stroke: tok("--surface"), "stroke-width": 2 }));
        }
        if (!narrow && (s.is_us || s === leader)) labelled.push({ s: s, ly: ly, last: last });
        else if (narrow && s.is_us) svg.appendChild(svgEl("text", { x: lx - 8, y: ly - 10, "text-anchor": "end", "font-size": 12, "font-weight": 600, fill: tok("--ink"), text: fmtNum(last) }));
      });
      labelled.sort(function (a, b) { return a.ly - b.ly; });
      var lastY = -Infinity;
      labelled.forEach(function (lbl) {
        var ty = Math.max(lbl.ly, lastY + 14); lastY = ty;
        if (ty !== lbl.ly) svg.appendChild(svgEl("line", { x1: W - m.r + 4, x2: W - m.r + 12, y1: lbl.ly, y2: ty, stroke: tok("--axis"), "stroke-width": 1 }));
        svg.appendChild(svgEl("text", { x: W - m.r + 16, y: ty + 4, "font-size": 12, fill: tok(lbl.s.is_us ? "--ink" : "--ink-2"), "font-weight": lbl.s.is_us ? 600 : 400, text: lbl.s.name + "  " + fmtNum(lbl.last) }));
      });
      var cross = svgEl("line", { x1: 0, x2: 0, y1: m.t, y2: H - m.b, stroke: tok("--axis"), "stroke-width": 1, opacity: 0 });
      svg.appendChild(cross);
      plot.appendChild(svg);
      plot.appendChild(legend([{ label: DOC.team.name, color: tok("--us") }, { label: "Other teams in the division", color: tok("--other") }]));
      var tip = tooltip(plot);
      svg.addEventListener("pointermove", function (ev) {
        var rect = svg.getBoundingClientRect(), px = (ev.clientX - rect.left) * W / rect.width;
        var i = 0, best = Infinity; weeks.forEach(function (w, k) { var d = Math.abs(x(k) - px); if (d < best) { best = d; i = k; } });
        cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", 1);
        var rows = teams.map(function (s) { return { label: s.name, value: fmtNum(s.cumulative[i]), color: s.is_us ? tok("--us") : tok("--other") }; });
        tip.show(ev.clientX - rect.left, ev.clientY - rect.top, "Through week " + weeks[i], rows);
      });
      svg.addEventListener("pointerleave", function () { cross.setAttribute("opacity", 0); tip.hide(); });
    }, function () {
      var cols = [{ key: "name", label: "Team" }].concat(weeks.map(function (w) { return { key: "w" + w, label: "Wk " + w, num: true }; }));
      return table(cols, teams.map(function (s) { var r = { name: s.name + (s.is_us ? " (us)" : "") }; weeks.forEach(function (w, i) { r["w" + w] = fmtNum(s.cumulative[i]); }); return r; }));
    });
  }

  // ---- week by week ------------------------------------------------------------------
  function renderWeeks() {
    var fig = document.getElementById("fig-weeks"), weeks = DOC.season.weeks;
    figure(fig, "Team matches", DOC.season.record.played + " played of " + weeks.length + " scheduled", function (plot) {
      var t = el("table", { class: "data" });
      t.appendChild(el("thead", null, [el("tr", null, ["Wk", "Date", "Opponent", "", "Result", "Score", "Boards"].map(function (h, i) { return el("th", { class: i >= 4 ? "num" : "", text: h }); }))]));
      var tb = el("tbody");
      weeks.forEach(function (w) {
        var chip = w.result ? el("span", { class: "chip " + w.result, text: w.result }) : w.pending_scoresheet ? el("span", { class: "chip pending", text: "pending" }) : el("span", { class: "chip none", text: w.scored ? "–" : "–" });
        tb.appendChild(el("tr", null, [
          el("td", { class: "num", text: w.week === null ? "" : String(w.week) }), el("td", { text: shortDate(w.date) }),
          el("td", { text: w.opponent || "" }), el("td", { text: w.home ? "home" : "away" }),
          el("td", { class: "num" }, [chip]),
          el("td", { class: "num", text: w.our_score === null ? "" : fmtNum(w.our_score) + "–" + fmtNum(w.their_score) }),
          el("td", { class: "num", text: w.games_won === null ? "" : w.games_won + " of " + w.games_played }),
        ]));
      });
      t.appendChild(tb); var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
    }, function () {
      return table([{ key: "week", label: "Wk", num: true }, { key: "date", label: "Date" }, { key: "opponent", label: "Opponent" }, { key: "home", label: "Site" }, { key: "result", label: "Result" }, { key: "score", label: "Score", num: true }, { key: "boards", label: "Boards", num: true }],
        weeks.map(function (w) { return { week: w.week, date: shortDate(w.date), opponent: w.opponent, home: w.home ? "home" : "away", result: w.result || (w.pending_scoresheet ? "pending" : "–"), score: w.our_score === null ? null : fmtNum(w.our_score) + "–" + fmtNum(w.their_score), boards: w.games_won === null ? null : w.games_won + " of " + w.games_played }; }));
    });
  }

  // ---- players table with sparklines and win bars -----------------------------
  function renderPlayers() {
    var fig = document.getElementById("fig-players"), players = currentPlayers();
    var game = DOC.team.game;
    figure(fig, "Roster", players.length + " player" + (players.length === 1 ? "" : "s"), function (plot) {
      var t = el("table", { class: "data" });
      var heads = ["Player", "SL", "SL this season", "Boards", "W–L", "Win %", "", "Form", game === "eight" ? "Avg race margin" : "Avg points margin", "Pts / board", game === "eight" ? "8OB / B&R" : "9OS / B&R", "APA W–P"];
      t.appendChild(el("thead", null, [el("tr", null, heads.map(function (h, i) { return el("th", { class: [3, 4, 5, 8, 9, 10, 11].indexOf(i) >= 0 ? "num" : "", text: h }); }))]));
      var tb = el("tbody");
      players.forEach(function (p) {
        var readings = p.skill_readings.map(function (r) { return r.skill_level; });
        var form = el("span");
        p.lines.forEach(function (l) { form.appendChild(el("span", { class: "chip " + (l.result || "none"), title: "Wk " + l.week + " vs SL " + l.opponent_skill_level + (l.score ? " · " + l.score : ""), text: l.result || "?", style: "margin-right:3px;min-width:22px;padding:1px 4px" })); });
        var bar = el("div", { class: "bar-track" }, [el("i", { style: "width:" + Math.round((p.win_pct || 0) * 100) + "%" })]);
        tb.appendChild(el("tr", null, [
          el("td", { text: p.name }), el("td", { class: "num", text: p.skill_level === null ? "–" : String(p.skill_level) }),
          el("td", null, [readings.length ? sparkline(readings, 90, 22, tok("--us")) : el("span", { class: "note", text: "no sheets" }), el("span", { class: "note", text: readings.length ? "  " + readings[0] + " → " + readings[readings.length - 1] : "" })]),
          el("td", { class: "num", text: String(p.games) }), el("td", { class: "num", text: p.wins + "–" + p.losses }),
          el("td", { class: "num", text: fmtPct(p.win_pct) }), el("td", null, [bar]), el("td", null, [form]),
          el("td", { class: "num", text: p.avg_margin === null ? "–" : (p.avg_margin > 0 ? "+" : "") + fmtNum(p.avg_margin * 100, 0) + "%" }),
          el("td", { class: "num", text: fmtNum(p.avg_points, 1) }), el("td", { class: "num", text: p.on_break + " / " + p.break_and_run }),
          el("td", { class: "num", text: p.apa_played === null ? "–" : (p.apa_won === null ? "?" : p.apa_won) + "–" + p.apa_played }),
        ]));
      });
      t.appendChild(tb); var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
      plot.appendChild(el("p", { class: "note", text: "Margin: how far along the race each side got, ours minus theirs, so +100% is a shutout and −100% is being shut out. Pts / board is APA match points earned per scoresheet line." }));
    }, function () {
      return table([{ key: "name", label: "Player" }, { key: "sl", label: "SL", num: true }, { key: "games", label: "Boards", num: true }, { key: "wl", label: "W–L", num: true }, { key: "pct", label: "Win %", num: true }, { key: "margin", label: "Avg margin", num: true }, { key: "pts", label: "Pts/board", num: true }, { key: "apa", label: "APA W–P", num: true }],
        players.map(function (p) { return { name: p.name, sl: p.skill_level, games: p.games, wl: p.wins + "–" + p.losses, pct: fmtPct(p.win_pct), margin: p.avg_margin === null ? null : fmtNum(p.avg_margin * 100, 0) + "%", pts: fmtNum(p.avg_points, 1), apa: p.apa_played === null ? null : p.apa_won + "–" + p.apa_played }; }));
    });
  }

  // ---- margins dot plot: every board, by week ----------------------------------------
  function renderMargins() {
    var fig = document.getElementById("fig-margins"), players = currentPlayers();
    var lines = []; players.forEach(function (p) { p.lines.forEach(function (l) { if (l.margin !== null && l.week !== null) lines.push({ p: p, l: l }); }); });
    figure(fig, "How close each board was", lines.length + " boards with a race margin", function (plot) {
      if (!lines.length) { plot.appendChild(el("p", { class: "empty", text: "No boards with a captured game score yet." })); return; }
      var weeks = Array.from(new Set(lines.map(function (d) { return d.l.week; }))).sort(function (a, b) { return a - b; });
      var W = 420, H = 260, m = { t: 12, r: 12, b: 30, l: 44 };
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Race margin per board by week" });
      var x = function (w) { var i = weeks.indexOf(w); return m.l + (weeks.length === 1 ? (W - m.l - m.r) / 2 : (i + 0.5) * (W - m.l - m.r) / weeks.length); };
      var y = function (v) { return m.t + (H - m.t - m.b) * (1 - (v + 1) / 2); };
      [-1, -0.5, 0, 0.5, 1].forEach(function (v) {
        svg.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: tok(v === 0 ? "--axis" : "--grid"), "stroke-width": 1 }));
        svg.appendChild(svgEl("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: tok("--muted"), text: (v > 0 ? "+" : "") + Math.round(v * 100) + "%" }));
      });
      weeks.forEach(function (w) { svg.appendChild(svgEl("text", { x: x(w), y: H - 10, "text-anchor": "middle", "font-size": 11, fill: tok("--muted"), text: "Wk " + w })); });
      var tip = tooltip(plot);
      // spread same-week dots horizontally so they never stack on one pixel
      var byWeek = {}; lines.forEach(function (d) { (byWeek[d.l.week] = byWeek[d.l.week] || []).push(d); });
      Object.keys(byWeek).forEach(function (w) {
        var group = byWeek[w].sort(function (a, b) { return b.l.margin - a.l.margin; }), n = group.length;
        group.forEach(function (d, i) {
          var cx = x(Number(w)) + (n === 1 ? 0 : (i - (n - 1) / 2) * 11), cy = y(d.l.margin);
          var color = d.l.result === "W" ? tok("--us") : tok("--them");
          var hit = svgEl("circle", { cx: cx, cy: cy, r: 12, fill: "transparent", tabindex: 0, role: "img", "aria-label": d.p.name + " week " + w + " " + d.l.score });
          var dot = svgEl("circle", { cx: cx, cy: cy, r: 4.5, fill: color, stroke: tok("--surface"), "stroke-width": 2, "pointer-events": "none" });
          function show(ev) {
            var rect = svg.getBoundingClientRect();
            tip.show((cx) * rect.width / W, cy * rect.height / H, d.p.name + " · Wk " + w + " vs SL " + d.l.opponent_skill_level,
              [{ label: d.l.result === "W" ? "Won" : "Lost", value: d.l.score, color: color }, { label: "Race", value: d.l.own_target + " vs " + d.l.opp_target }, { label: "Margin", value: (d.l.margin > 0 ? "+" : "") + Math.round(d.l.margin * 100) + "%" }]);
          }
          hit.addEventListener("pointerenter", show); hit.addEventListener("focus", show);
          hit.addEventListener("pointerleave", tip.hide); hit.addEventListener("blur", tip.hide);
          svg.appendChild(hit); svg.appendChild(dot);
        });
      });
      plot.appendChild(svg);
      plot.appendChild(legend([{ label: "Won", color: tok("--us") }, { label: "Lost", color: tok("--them") }], "rect"));
    }, function () {
      return table([{ key: "week", label: "Wk", num: true }, { key: "name", label: "Player" }, { key: "opp", label: "Opp SL", num: true }, { key: "result", label: "Result" }, { key: "score", label: "Score", num: true }, { key: "race", label: "Race", num: true }, { key: "margin", label: "Margin", num: true }],
        lines.map(function (d) { return { week: d.l.week, name: d.p.name, opp: d.l.opponent_skill_level, result: d.l.result, score: d.l.score, race: d.l.own_target + " vs " + d.l.opp_target, margin: (d.l.margin > 0 ? "+" : "") + Math.round(d.l.margin * 100) + "%" }; }));
    });
  }

  // ---- win rate by skill-level gap: one-hue bars --------------------------------------
  function renderDelta() {
    var fig = document.getElementById("fig-delta"), players = currentPlayers();
    var agg = {}; players.forEach(function (p) { p.vs_skill_delta.forEach(function (b) { var a = agg[b.delta] = agg[b.delta] || { delta: b.delta, games: 0, wins: 0 }; a.games += b.games; a.wins += b.wins; }); });
    var buckets = Object.keys(agg).map(Number).sort(function (a, b) { return a - b; }).map(function (k) { return agg[k]; });
    figure(fig, "Win rate by skill-level gap", "opponent SL minus ours", function (plot) {
      if (!buckets.length) { plot.appendChild(el("p", { class: "empty", text: "No boards yet." })); return; }
      var W = 420, H = 260, m = { t: 16, r: 12, b: 34, l: 44 }, bw = Math.min(24, (W - m.l - m.r) / buckets.length - 8);
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Win rate by skill level gap" });
      var x = function (i) { return m.l + (i + 0.5) * (W - m.l - m.r) / buckets.length; };
      var y = function (v) { return m.t + (H - m.t - m.b) * (1 - v); };
      [0, 0.25, 0.5, 0.75, 1].forEach(function (v) {
        svg.appendChild(svgEl("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: tok(v === 0 ? "--axis" : "--grid"), "stroke-width": 1 }));
        svg.appendChild(svgEl("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end", "font-size": 11, fill: tok("--muted"), text: Math.round(v * 100) + "%" }));
      });
      var tip = tooltip(plot);
      buckets.forEach(function (b, i) {
        var rate = b.games ? b.wins / b.games : 0, top = y(rate), h = Math.max(0, y(0) - top);
        var g = svgEl("g", { tabindex: 0, role: "img", "aria-label": "Gap " + b.delta + ": " + b.wins + " of " + b.games });
        var path = "M" + (x(i) - bw / 2) + "," + y(0) + " v" + (-(h - Math.min(4, h))) + " a4,4 0 0 1 4,-4 h" + (bw - 8) + " a4,4 0 0 1 4,4 v" + (h - Math.min(4, h)) + " z";
        g.appendChild(svgEl("rect", { x: x(i) - bw / 2 - 6, y: m.t, width: bw + 12, height: H - m.t - m.b, fill: "transparent" }));
        g.appendChild(svgEl("path", { d: h >= 4 ? path : "M" + (x(i) - bw / 2) + "," + y(0) + " h" + bw + " v" + (-h) + " h" + (-bw) + " z", fill: tok("--us") }));
        svg.appendChild(svgEl("text", { x: x(i), y: top - 6, "text-anchor": "middle", "font-size": 11, fill: tok("--ink-2"), text: b.wins + "/" + b.games }));
        svg.appendChild(svgEl("text", { x: x(i), y: H - 12, "text-anchor": "middle", "font-size": 11, fill: tok("--muted"), text: (b.delta > 0 ? "+" : "") + b.delta }));
        function show() { var rect = svg.getBoundingClientRect(); tip.show(x(i) * rect.width / W, top * rect.height / H, "Opponent " + (b.delta === 0 ? "same SL" : (b.delta > 0 ? b.delta + " higher" : (-b.delta) + " lower")), [{ label: "Win rate", value: fmtPct(rate) }, { label: "Boards", value: b.wins + " won of " + b.games }]); }
        g.addEventListener("pointerenter", show); g.addEventListener("focus", show); g.addEventListener("pointerleave", tip.hide); g.addEventListener("blur", tip.hide);
        svg.appendChild(g);
      });
      plot.appendChild(svg);
      plot.appendChild(el("p", { class: "note", text: "Negative gap: we had the higher skill level. Labels are wins / boards." }));
    }, function () {
      return table([{ key: "delta", label: "Gap", num: true }, { key: "games", label: "Boards", num: true }, { key: "wins", label: "Wins", num: true }, { key: "pct", label: "Win %", num: true }],
        buckets.map(function (b) { return { delta: (b.delta > 0 ? "+" : "") + b.delta, games: b.games, wins: b.wins, pct: fmtPct(b.games ? b.wins / b.games : null) }; }));
    });
  }

  // ---- lineup matrix ---------------------------------------------------------------------
  function renderLineup() {
    var fig = document.getElementById("fig-lineup"), lu = DOC.lineup, rows = lu.rows.filter(function (r) { return !state.player || r.name === state.player; });
    figure(fig, "Boards by week", lu.weeks.length + " scheduled weeks", function (plot) {
      var t = el("table", { class: "data" });
      t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "Player" }), el("th", { class: "num", text: "SL" })].concat(lu.weeks.map(function (w) { return el("th", { class: "num", text: "Wk " + w }); })).concat([el("th", { class: "num", text: "Boards" })]))]));
      var tb = el("tbody");
      rows.forEach(function (r) {
        var total = r.cells.reduce(function (a, c) { return a + c.length; }, 0);
        tb.appendChild(el("tr", null, [el("td", { text: r.name }), el("td", { class: "num", text: r.skill_level === null ? "–" : String(r.skill_level) })]
          .concat(r.cells.map(function (c) { var td = el("td", { class: "num" }); c.forEach(function (g) { td.appendChild(el("span", { class: "chip " + (g.result || "none"), title: g.score || "", text: g.result || "?", style: "margin-left:3px" })); }); return td; }))
          .concat([el("td", { class: "num", text: String(total) })])));
      });
      t.appendChild(tb); var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
    }, function () {
      var cols = [{ key: "name", label: "Player" }].concat(lu.weeks.map(function (w) { return { key: "w" + w, label: "Wk " + w }; }));
      return table(cols, rows.map(function (r) { var o = { name: r.name }; lu.weeks.forEach(function (w, i) { o["w" + w] = r.cells[i].map(function (g) { return g.result + (g.score ? " " + g.score : ""); }).join(", ") || "–"; }); return o; }));
    });
  }

  // ---- race chart ------------------------------------------------------------------------
  function renderRace() {
    var fig = document.getElementById("fig-race"), race = DOC.race;
    document.getElementById("race-lede").textContent = race.format === "eight"
      ? "Games each side needs to win, by skill level. " + race.winners_agreeing + " of " + race.winners_checked + " of our winning boards reached exactly the chart's target."
      : race.format === "nine" ? "Points each skill level needs to win. " + race.winners_agreeing + " of " + race.winners_checked + " of our winning boards reached exactly the chart's target." : "";
    figure(fig, race.format === "eight" ? "8-Ball race (games to win)" : "9-Ball race (points to win)", race.source, function (plot) {
      var t = el("table", { class: "data" });
      if (race.format === "nine") {
        t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "Skill level" }), el("th", { class: "num", text: "Points to win" })])]));
        var tb = el("tbody"); Object.keys(race.chart).forEach(function (sl) { tb.appendChild(el("tr", null, [el("td", { text: "SL " + sl }), el("td", { class: "num", text: String(race.chart[sl]) })])); }); t.appendChild(tb);
      } else if (race.format === "eight") {
        var levels = [2, 3, 4, 5, 6, 7];
        t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: "Ours ↓ / theirs →" })].concat(levels.map(function (l) { return el("th", { class: "num", text: "SL " + l }); })))]));
        var body = el("tbody"); levels.forEach(function (a) { body.appendChild(el("tr", null, [el("td", { text: "SL " + a })].concat(levels.map(function (b) { var r = race.chart[a + "-" + b]; return el("td", { class: "num", text: r ? r[0] + "–" + r[1] : "–" }); })))); }); t.appendChild(body);
      } else { plot.appendChild(el("p", { class: "empty", text: "Format unknown." })); return; }
      var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
    }, function () { return el("p", { class: "note", text: "The chart above is already a table." }); });
  }

  // ---- seasons --------------------------------------------------------------------------
  function renderHistory() {
    var fig = document.getElementById("fig-history"), sessions = DOC.history;
    figure(fig, "Season by season", sessions.length + " season" + (sessions.length === 1 ? "" : "s") + " captured", function (plot) {
      if (sessions.length <= 1) plot.appendChild(el("p", { class: "note", text: "Only the current season is captured so far." }));
      var W = 760, H = 48 + sessions.length * 34, m = { t: 10, r: 120, b: 26, l: 150 };
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, role: "img", "aria-label": "Team win rate by season" });
      var x = function (v) { return m.l + v * (W - m.l - m.r); };
      [0, 0.25, 0.5, 0.75, 1].forEach(function (v) { svg.appendChild(svgEl("line", { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b, stroke: tok(v === 0 ? "--axis" : "--grid"), "stroke-width": 1 })); svg.appendChild(svgEl("text", { x: x(v), y: H - 8, "text-anchor": "middle", "font-size": 11, fill: tok("--muted"), text: Math.round(v * 100) + "%" })); });
      var tip = tooltip(plot);
      sessions.forEach(function (s, i) {
        var cy = m.t + 12 + i * 34, rate = s.win_pct || 0, w = x(rate) - x(0);
        svg.appendChild(svgEl("text", { x: m.l - 10, y: cy + 4, "text-anchor": "end", "font-size": 12.5, fill: tok(s.is_current ? "--ink" : "--ink-2"), "font-weight": s.is_current ? 600 : 400, text: (s.session_name || "?") + (s.format ? " · " + fmtLabel(s.format) : "") }));
        var g = svgEl("g", { tabindex: 0, role: "img", "aria-label": (s.session_name || "") + " " + s.wins + " wins " + s.losses + " losses" });
        g.appendChild(svgEl("rect", { x: x(0), y: cy - 14, width: W - m.l - m.r + m.r, height: 28, fill: "transparent" }));
        g.appendChild(svgEl("path", { d: w > 4 ? "M" + x(0) + "," + (cy - 9) + " h" + (w - 4) + " a4,4 0 0 1 4,4 v10 a4,4 0 0 1 -4,4 h" + (-(w - 4)) + " z" : "M" + x(0) + "," + (cy - 9) + " h" + Math.max(w, 0) + " v18 h" + (-Math.max(w, 0)) + " z", fill: tok(s.is_current ? "--us" : "--other") }));
        svg.appendChild(svgEl("text", { x: x(rate) + 8, y: cy + 4, "font-size": 12, fill: tok("--ink-2"), "font-variant-numeric": "tabular-nums", text: s.wins + "–" + s.losses + (s.ties ? "–" + s.ties : "") + (s.final_rank ? "  ·  rank " + s.final_rank : "") }));
        function show() { var rect = svg.getBoundingClientRect(); tip.show(x(rate) * rect.width / W, (cy - 10) * rect.height / H, s.session_name, [{ label: "Record", value: s.wins + "–" + s.losses }, { label: "Points", value: fmtNum(s.points_for) + " for, " + fmtNum(s.points_against) + " against" }, { label: "Players", value: String(s.players.length) }]); }
        g.addEventListener("pointerenter", show); g.addEventListener("focus", show); g.addEventListener("pointerleave", tip.hide); g.addEventListener("blur", tip.hide);
        svg.appendChild(g);
      });
      plot.appendChild(svg);
      // per-season player detail
      var sel = sessions.filter(function (s) { return s.session_name === state.session; })[0] || sessions[sessions.length - 1];
      if (sel && sel.players.length) {
        var t = el("table", { class: "data" });
        t.appendChild(el("thead", null, [el("tr", null, [el("th", { text: (sel.session_name || "") + " roster" }), el("th", { class: "num", text: "Boards" }), el("th", { class: "num", text: "W–L" }), el("th", { class: "num", text: "Win %" }), el("th", { class: "num", text: "SL start → end" })])]));
        var tb = el("tbody");
        sel.players.filter(function (p) { return !state.player || p.name === state.player; }).forEach(function (p) {
          tb.appendChild(el("tr", null, [el("td", { text: p.name }), el("td", { class: "num", text: String(p.games) }), el("td", { class: "num", text: p.wins + "–" + (p.games - p.wins) }), el("td", { class: "num", text: fmtPct(p.win_pct) }), el("td", { class: "num", text: (p.skill_level_start === null ? "–" : p.skill_level_start) + " → " + (p.skill_level_end === null ? "–" : p.skill_level_end) })]));
        });
        t.appendChild(tb); var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
      }
    }, function () {
      return table([{ key: "session", label: "Season" }, { key: "format", label: "Format" }, { key: "record", label: "Record", num: true }, { key: "pct", label: "Win %", num: true }, { key: "pf", label: "Points for", num: true }, { key: "pa", label: "Points against", num: true }, { key: "rank", label: "Rank", num: true }],
        sessions.map(function (s) { return { session: s.session_name, format: fmtLabel(s.format), record: s.wins + "–" + s.losses, pct: fmtPct(s.win_pct), pf: fmtNum(s.points_for), pa: fmtNum(s.points_against), rank: s.final_rank }; }));
    });
  }

  // ---- lifetime -------------------------------------------------------------------------
  function renderCareer() {
    var fig = document.getElementById("fig-career"), rows = DOC.career.filter(function (r) { return !state.player || r.name === state.player; });
    figure(fig, "Lifetime, per APA", rows.length ? rows.length + " row" + (rows.length === 1 ? "" : "s") : "", function (plot) {
      if (!rows.length) { plot.appendChild(el("p", { class: "empty", text: "APA exposes lifetime stats only for the signed-in member; the career backfill adds the rest where the account can see them." })); return; }
      var t = el("table", { class: "data" });
      t.appendChild(el("thead", null, [el("tr", null, ["Player", "Format", "Scope", "W–P", "Win %", "Last 2 yrs", "On break", "B&R", "Mini slams", "Def. shot avg", "Last played"].map(function (h, i) { return el("th", { class: i >= 3 && i <= 9 ? "num" : "", text: h }); }))]));
      var tb = el("tbody");
      rows.forEach(function (r) { tb.appendChild(el("tr", null, [el("td", { text: r.name || "" }), el("td", { text: fmtLabel(r.format) }), el("td", { text: r.scope }), el("td", { class: "num", text: (r.matches_won === null ? "–" : r.matches_won) + "–" + (r.matches_played === null ? "–" : r.matches_played) }), el("td", { class: "num", text: fmtPct(r.win_pct) }), el("td", { class: "num", text: fmtNum(r.matches_last_two_years) }), el("td", { class: "num", text: fmtNum(r.on_break) }), el("td", { class: "num", text: fmtNum(r.break_and_runs) }), el("td", { class: "num", text: fmtNum(r.mini_slams) }), el("td", { class: "num", text: fmtNum(r.defensive_shot_avg, 2) }), el("td", { text: r.last_played || "–" })])); });
      t.appendChild(tb); var wrap = el("div", { class: "scroll" }); wrap.appendChild(t); plot.appendChild(wrap);
    }, function () { return el("p", { class: "note", text: "Already a table." }); });
  }

  function renderAll() {
    var note = document.getElementById("f-note");
    note.textContent = isCurrentSeason() ? "" : "Earlier season: the Seasons section updates; the current-season charts stay on " + DOC.team.session_name + ".";
    renderPlayers(); renderMargins(); renderDelta(); renderLineup(); renderHistory(); renderCareer();
  }
  renderHeader(); renderTrajectory(); renderWeeks(); renderRace(); renderAll();
  document.getElementById("footer").textContent = "Built " + new Date(DOC.built_at).toLocaleString() + " from the promoted APA-Tracker database. Every figure traces to a captured match, scoresheet line, roster row or standings snapshot; the race chart is APA's published table.";
})();
</script>
"""


def render_team_analytics_html(doc: dict[str, Any]) -> str:
    """Self-contained page for one team's analytics document."""
    title = f"{doc['team']['name']} Analytics"
    payload = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__TITLE__", escape(title)).replace("__DATA__", payload)
