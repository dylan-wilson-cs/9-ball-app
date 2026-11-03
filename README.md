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
