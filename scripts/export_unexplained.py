"""Export every `unexplained` mistake (pointsLost >= 5, no detector fired) for detector work.

Usage (from apps/api):
    uv run python ../../scripts/export_unexplained.py --out ../../data/unexplained

Each folder has the golden-case layout (position.sgf + both analyses) and a notes.md, so a new
detector's golden cases can start from them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session

from ishi.config import get_settings
from ishi.db.session import get_engine
from ishi.play.review_service import export_unexplained


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("../../data/unexplained"))
    args = ap.parse_args()
    with Session(get_engine(get_settings().db_path)) as session:
        folders = export_unexplained(session, args.out)
    print(f"exported {len(folders)} unexplained mistakes to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
