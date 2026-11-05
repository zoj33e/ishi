"""Rank estimate with the database and KataGo (M8): per-game move likelihood, the daily snapshot
and the adaptive bot strength. The math lives in `ishi.progress.rank`."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlmodel import Session, col, select

from ishi.db.models import Game, RankHistory, User, utcnow
from ishi.engine.katago_process import KataGoProcess
from ishi.engine.queries import human_policy_query
from ishi.gym.service import local_now
from ishi.progress import rank as rk
from ishi.rules.board import Color
from ishi.rules.coords import point_to_index
from ishi.rules.game import GameState

log = logging.getLogger("ishi.progress")

LIKELIHOOD_PRIORITY = -20  # behind the post-game review


def learner_turns(state: GameState, learner: Color) -> list[int]:
    """Positions before the learner's own moves (passes and the opening skipped)."""
    return [
        t
        for t, m in enumerate(state.moves)
        if t >= rk.SKIP_OPENING and m.color is learner and m.point is not None
    ]


async def game_likelihood(
    engine: KataGoProcess, state: GameState, learner: Color, qid: str
) -> dict[str, float]:
    """Summed log-likelihood of the learner's moves under each HumanSL profile."""
    turns = learner_turns(state, learner)
    out: dict[str, float] = {"moves": float(len(turns))}
    if not turns:
        return out

    async def one(profile: str) -> tuple[str, float]:
        q = human_policy_query(f"{qid}-{profile}", state, turns, profile)
        q.priority = LIKELIHOOD_PRIORITY
        total = 0.0
        for resp in await engine.analyze(q, timeout=120.0):
            move = state.moves[resp.turnNumber]
            assert move.point is not None and resp.humanPolicy is not None
            total += rk.move_logl(resp.humanPolicy, point_to_index(move.point, state.size))
        return profile, round(total, 3)

    out.update(await asyncio.gather(*(one(p) for p in rk.LIKELIHOOD_PROFILES)))
    return out


def finished_full_games(session: Session, user_id: str) -> list[Game]:
    """Finished 9x9 games (exams included), newest first."""
    return list(
        session.exec(
            select(Game)
            .where(Game.user_id == user_id, Game.mode == "full", Game.status == "finished")
            .order_by(col(Game.updated_at).desc())
        )
    )


def update_rank(session: Session, user: User, today: date | None = None) -> rk.RankEstimate:
    """Recompute the estimate from the recent games, set the bot strength, snapshot the day."""
    games = finished_full_games(session, user.id)
    results = [
        (g.bot_rank, bool(g.learner_won))
        for g in games[: rk.RESULT_GAMES]
        if g.bot_rank is not None
    ]
    logl: dict[float, float] = {}
    moves = 0
    for g in [g for g in games if g.likelihood][: rk.RECENT_GAMES]:
        assert g.likelihood is not None
        moves += int(g.likelihood.get("moves", 0))
        for profile, r in rk.LIKELIHOOD_PROFILES.items():
            if profile in g.likelihood:
                logl[r] = logl.get(r, 0.0) + g.likelihood[profile]
    est = rk.estimate(rk.BELT_PRIOR.get(user.belt, 30.0), results, logl, moves)
    recent = [bool(g.learner_won) for g in reversed(games) if g.exam_id is None]
    user.rank_estimate = est.rank
    user.bot_rank = rk.adaptive_bot_rank(est.rank, recent)
    user.updated_at = utcnow()
    session.add(user)
    day = today or local_now().date()
    row = session.exec(
        select(RankHistory).where(RankHistory.user_id == user.id, RankHistory.date == day)
    ).first() or RankHistory(user_id=user.id, date=day, rank_estimate=est.rank)
    row.rank_estimate = est.rank
    row.likelihood_rank = est.likelihood_rank
    row.results_rank = est.results_rank
    row.games_count = len(games)
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    log.info(
        "rank user=%s estimate=%.1f (likelihood %s, results %.1f) bot=%.0f",
        user.id,
        est.rank,
        est.likelihood_rank,
        est.results_rank,
        user.bot_rank,
    )
    return est


def default_bot_rank(user: User) -> float:
    """Today's 9x9 bot: the adaptive strength, or one stone below the belt's rank to start."""
    if user.bot_rank is not None:
        return user.bot_rank
    return rk.adaptive_bot_rank(rk.BELT_PRIOR.get(user.belt, 30.0), [])
