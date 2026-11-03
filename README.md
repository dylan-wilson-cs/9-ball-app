# sv

Everything you need to build a Svelte project, powered by [`sv`](https://github.com/sveltejs/cli).

## Creating a project

If you're seeing this, you've probably already done this step. Congrats!

```bash
# create a new project in the current directory
npx sv create

# create a new project in my-app
npx sv create my-app
```

## Developing

Once you've created a project and installed dependencies with `npm install` (or `pnpm install` or `yarn`), start a development server:

```bash
npm run dev

# or start the server and open the app in a new browser tab
npm run dev -- --open
```

## Building

To create a production version of your app:

```bash
npm run build
```

You can preview the production build with `npm run preview`.

> To deploy your app, you may need to install an [adapter](https://svelte.dev/docs/kit/adapters) for your target environment.

## APA-Tracker (vendored)

`APA-Tracker/` is a vendored copy of
[ssands5-cloud/APA-Tracker](https://github.com/ssands5-cloud/APA-Tracker), a
Python tool that pulls APA league standings, rosters, and match history into
SQLite and builds Excel exports and static coach dashboards. See
`APA-Tracker/UPSTREAM.md` for the pinned upstream commit and
`APA-Tracker/README.md` for its own documentation.

It is independent of the SvelteKit app above: Python 3.12/3.13, Playwright,
and pytest, no Node involvement.

### Remote (Claude Code cloud) setup

```bash
bash APA-Tracker/setup_remote.sh
```

The script creates `APA-Tracker/.venv`, installs the pinned lock
(`requirements-dev.txt`), and puts the Chromium build Playwright expects in
`APA-Tracker/.pw-browsers` (gitignored). It downloads the exact pinned
revision from `cdn.playwright.dev`; if the environment's network policy blocks
that host, it falls back to mapping the container's preinstalled Chromium onto
the expected revision. Either way, export
`PLAYWRIGHT_BROWSERS_PATH="$PWD/APA-Tracker/.pw-browsers"` before running
pytest.

To run it automatically for every new session, add this line to the cloud
environment's Setup script:

```bash
cd 9-ball-app && bash APA-Tracker/setup_remote.sh
```

Credentials (`APA_USERNAME`, `APA_PASSWORD`, `APA_ACCESS_TOKEN`) go in the
environment's secrets, never in the repo.

### Remote access to the dashboards

APA-Tracker has no server mode; its output is static, self-contained HTML.
Remote access therefore means: refresh the data in a cloud session, then
publish the resulting dashboard files somewhere you can open from a phone or
any browser (for example as a private claude.ai artifact).

The refresh step is unattended:

```bash
cd APA-Tracker
source .venv/bin/activate
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.pw-browsers"
python scripts/remote_refresh.py            # every team the account plays on
python scripts/remote_refresh.py --resume   # continue if the token expired mid-run
```

`scripts/remote_refresh.py` logs into APA Member Services headlessly with
`APA_USERNAME` / `APA_PASSWORD` from the environment (or uses an existing
`APA_ACCESS_TOKEN` if one is set), captures the short-lived token the APA
site attaches to its own API calls, and hands it in memory to the upstream
game-night launcher, which does the live refresh, verification, per-team
Coach Cockpit builds, and database promotion. The verified pages land in:

```
APA-Tracker/exports/remote/<team_id>/dashboard.html   one file per team
APA-Tracker/exports/remote/manifest.json              team names, build time, source hash
```

Each `dashboard.html` is one file with no external links, ready to publish
as-is. The password and token are never written to disk or logged.
