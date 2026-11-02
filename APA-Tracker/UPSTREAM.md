# Upstream

This directory is a vendored copy of a separate repository, not code
originally written in `9-ball-app`.

- Source: https://github.com/ssands5-cloud/APA-Tracker
- Branch: `main`
- Commit: `add65727eb66e23566dcaf50e476f89dcdc80921` (2026-09-21, "Merge PR #80: normalize real APA 8-ball and 9-ball labels")
- Vendored: 2026-11-02, with the upstream `.git` directory removed.

`AGENTS.md` and `.repo-boundary-id` belong to the upstream author's local
tooling (a machine-level git guard pinned to a Windows path) and have no
effect here.

To pull upstream changes later, clone the source to a scratch location and
copy the tree over this directory, then update the commit hash above.
