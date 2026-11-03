#!/usr/bin/env python3
"""Build the Team Analytics page for one team from a database snapshot.

    python scripts/build_team_analytics.py --db data/apa_tracker.db --team-id 13117798 --out exports/analytics

Writes <out>/<team_id>/analytics.html (self-contained) and analytics.json
(the exact document the page embeds). Reads the database read-only.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from analytics.team_analytics import build_team_analytics
from ui.team_analytics import render_team_analytics_html

logger = logging.getLogger("build_team_analytics")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "data" / "apa_tracker.db"
DEFAULT_OUT = PROJECT_ROOT / "exports" / "analytics"


def build(db_path: Path, team_id: str, out_dir: Path) -> tuple[Path, dict]:
    if not db_path.is_file():
        raise FileNotFoundError(f"no database at {db_path}")
    engine = create_engine(f"sqlite:///file:{db_path}?mode=ro&uri=true")
    try:
        with Session(engine) as db:
            doc = build_team_analytics(db, team_id)
    finally:
        engine.dispose()
    target = out_dir / str(team_id)
    target.mkdir(parents=True, exist_ok=True)
    html_path = target / "analytics.html"
    html_path.write_text(render_team_analytics_html(doc), encoding="utf-8")
    (target / "analytics.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s (%d bytes)", html_path, html_path.stat().st_size)
    return html_path, doc


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--team-id", required=True, action="append", help="APA team id; repeatable")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    for team_id in args.team_id:
        build(args.db, team_id, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
