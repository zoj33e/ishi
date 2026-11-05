"""M8 acceptance: a simulated learner (the HumanSL bot at a fixed rank, playing Black through the
real API) plays 10 games against Ishi's adaptive bot; the rank estimate should end within
±3 stones of the learner's true rank.

Every learner starts from the same Orange-belt guess (25k), so the estimate has to move there.

Usage (from apps/api, engine set up in .env):
    uv run python ../../scripts/rank_simulation.py --ranks 22 15 10 --games 10
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranks", type=float, nargs="+", default=[22.0, 15.0, 10.0])
    ap.add_argument("--games", type=int, default=10)
    ap.add_argument("--belt", default="orange")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    os.environ["ISHI_DEV_UNLOCK_ALL"] = "0"
    os.environ["ISHI_LLM_ENABLED"] = "false"

    from fastapi.testclient import TestClient
    from sqlmodel import Session, select

    from ishi.bots.humansl_bot import profile_for, rank_label
    from ishi.config import get_settings
    from ishi.db.models import Game, RankHistory
    from ishi.db.session import get_engine, get_or_create_user
    from ishi.main import create_app
    from ishi.play import service
    from ishi.play.full_game import bot_turn
    from ishi.rules.coords import point_to_gtp

    ok = True
    for true_rank in args.ranks:
        tmp = Path(tempfile.mkdtemp())
        os.environ["ISHI_DB_PATH"] = str(tmp / "sim.db")
        get_settings.cache_clear()
        rng = random.Random(args.seed)
        learner = profile_for(true_rank)
        print(f"\n== learner {rank_label(true_rank)} ({learner.profile}, T={learner.temperature})")
        with TestClient(create_app()) as api:
            t0 = time.time()
            while api.get("/api/health").json().get("engine") != "ok":
                if time.time() - t0 > 300:
                    print("engine did not start", file=sys.stderr)
                    return 2
                time.sleep(1)
            db = get_engine(get_settings().db_path)
            with Session(db) as s:
                user = get_or_create_user(s)
                user.belt = args.belt
                user.settings = {"nudges": False}
                s.add(user)
                s.commit()
            app = api.app
            for n in range(1, args.games + 1):
                g = api.post("/api/games", json={"mode": "full"}).json()
                gid, streak = g["id"], 0
                while True:
                    with Session(db) as s:
                        game = s.get(Game, gid)
                        assert game is not None
                        if game.status == "finished":
                            break
                        state = service.load_state(s, game)
                    turn = api.portal.call(  # type: ignore[union-attr]
                        lambda st=state, sk=streak: bot_turn(
                            app.state.engine,
                            st,
                            learner,
                            rng,
                            resign_streak=sk,
                            qid=f"sim-{gid}-{st.move_number}",
                        )
                    )
                    streak = turn.resign_streak
                    if turn.resign:
                        api.post(f"/api/games/{gid}/resign")
                        break
                    point = "pass" if turn.point is None else point_to_gtp(turn.point, 9)
                    r = api.post(f"/api/games/{gid}/moves", json={"point": point})
                    if r.status_code != 200:
                        print("move failed", r.json(), file=sys.stderr)
                        return 2
                api.portal.call(app.state.analysis.idle.wait)  # type: ignore[union-attr]
                with Session(db) as s:
                    game = s.get(Game, gid)
                    user = get_or_create_user(s)
                    assert game is not None
                    h = s.exec(
                        select(RankHistory).where(RankHistory.user_id == user.id)
                    ).first()
                    lk = (
                        "  -" if h is None or h.likelihood_rank is None
                        else f"{h.likelihood_rank:4.1f}"
                    )
                    rr = "  -" if h is None else f"{h.results_rank:4.1f}"
                    print(
                        f"game {n:2d}: bot {rank_label(game.bot_rank or 0):>4} "
                        f"{'won ' if game.learner_won else 'lost'} {game.result:<8} -> estimate "
                        f"{user.rank_estimate:5.1f} ({rank_label(user.rank_estimate or 0)}) "
                        f"[moves {lk}, results {rr}], next bot {rank_label(user.bot_rank or 0)}"
                    )
            with Session(db) as s:
                est = get_or_create_user(s).rank_estimate
        err = abs((est or 99) - true_rank)
        ok &= err <= 3
        print(f"-> estimate {est:.1f} vs true {true_rank:.0f}: off by {err:.1f} stones "
              f"({'ok' if err <= 3 else 'FAIL'}, accept <= 3)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
