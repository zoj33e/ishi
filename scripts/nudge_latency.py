"""Nudge latency (M7 accepts p95 < 1.5 s) with the real KataGo, through the real API in-process.

Plays full 9x9 games against the bot; after each bot move it waits `--think` seconds (the learner
looking at the board) and previews a few ghost moves: KataGo's worst-looking ones (likely nudges)
and random ones. The nudge budget is lifted so every preview runs the whole check.

Usage (from apps/api, engine set up in .env):
    uv run python ../../scripts/nudge_latency.py --games 4 --think 0.5
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4)
    ap.add_argument("--moves", type=int, default=24, help="learner moves per game")
    ap.add_argument("--previews", type=int, default=3, help="ghost moves per position")
    ap.add_argument("--think", type=float, default=0.5, help="seconds before the first preview")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--belt", default="green", help="learner belt (which concepts are open)")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp())
    os.environ["ISHI_DB_PATH"] = str(tmp / "latency.db")
    os.environ["ISHI_DEV_UNLOCK_ALL"] = "1"
    os.environ["ISHI_LLM_ENABLED"] = "false"

    from fastapi.testclient import TestClient
    from sqlmodel import Session, select

    from ishi.config import get_settings
    from ishi.db.models import User
    from ishi.db.session import get_engine
    from ishi.engine.katago_process import KataGoProcess
    from ishi.main import create_app
    from ishi.play import nudges

    get_settings.cache_clear()
    nudges.NUDGES_PER_GAME = 10_000  # measure the full check on every preview
    waits: list[float] = []
    queries: list[float] = []
    get0, analyze0 = nudges.LiveAnalysis.get, KataGoProcess.analyze

    async def get(self, *a, **k):  # type: ignore[no-untyped-def]
        t = time.perf_counter()
        try:
            return await get0(self, *a, **k)
        finally:
            waits.append(time.perf_counter() - t)

    async def analyze(self, query, *a, **k):  # type: ignore[no-untyped-def]
        t = time.perf_counter()
        try:
            return await analyze0(self, query, *a, **k)
        finally:
            if "nudge" in query.id:
                queries.append(time.perf_counter() - t)

    if os.environ.get("NO_BG"):
        from ishi.play.review_service import AnalysisWorker

        AnalysisWorker.enqueue = lambda self, gid: None  # type: ignore[method-assign]
    nudges.LiveAnalysis.get = get  # type: ignore[method-assign]
    KataGoProcess.analyze = analyze  # type: ignore[method-assign]
    rng = random.Random(args.seed)
    times: list[float] = []
    shown = 0
    with TestClient(create_app()) as api:
        t0 = time.time()
        while api.get("/api/health").json().get("engine") != "ok":
            if time.time() - t0 > 300:
                print("engine did not start", file=sys.stderr)
                return 2
            time.sleep(1)
        api.patch("/api/me", json={"settings": {"nudges": True}})
        with Session(get_engine(get_settings().db_path)) as db:
            for user in db.exec(select(User)).all():
                user.belt = args.belt
                db.add(user)
            db.commit()
        for g in range(args.games):
            game = api.post("/api/games", json={"mode": "full", "bot_rank": 20}).json()
            gid = game["id"]
            for _ in range(args.moves):
                state = api.get(f"/api/games/{gid}").json()
                if state["status"] == "finished":
                    break
                time.sleep(args.think)
                taken = set(state["stones"]["black"]) | set(state["stones"]["white"])
                empty = [
                    f"{c}{r}" for c in "ABCDEFGHJ" for r in range(1, 10) if f"{c}{r}" not in taken
                ]
                ghosts = rng.sample(empty, min(args.previews, len(empty)))
                for ghost in ghosts:
                    t = time.perf_counter()
                    r = api.post(f"/api/games/{gid}/preview", json={"point": ghost}).json()
                    times.append(time.perf_counter() - t)
                    shown += bool(r.get("nudge"))
                move = rng.choice(ghosts or ["pass"])
                r = api.post(f"/api/games/{gid}/moves", json={"point": move})
                if r.status_code != 200:
                    continue
            print(f"game {g + 1}: {len(times)} previews so far, {shown} nudges")
    times.sort()
    p95 = times[int(0.95 * (len(times) - 1))]
    print(
        f"{len(times)} previews, {shown} nudges; median {statistics.median(times) * 1000:.0f} ms,"
        f" p95 {p95 * 1000:.0f} ms, max {times[-1] * 1000:.0f} ms (accept p95 < 1500 ms)"
    )
    for name, xs in (("live wait", waits), ("after/human query", queries)):
        if xs:
            xs.sort()
            print(
                f"  {name}: n={len(xs)} median {statistics.median(xs) * 1000:.0f} ms,"
                f" p95 {xs[int(0.95 * (len(xs) - 1))] * 1000:.0f} ms, max {xs[-1] * 1000:.0f} ms"
            )
    return 0 if p95 < 1.5 else 1


if __name__ == "__main__":
    sys.exit(main())
