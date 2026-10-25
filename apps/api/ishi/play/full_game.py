"""Full-rule games against the HumanSL bot: one bot turn, and end-of-game scoring.

These talk to KataGo; the decisions themselves are pure functions in `ishi.bots.humansl_bot`
and `dead_stones` below.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from ishi.bots.humansl_bot import (
    BOT_VISITS,
    BotProfile,
    SearchSummary,
    choose_index,
    next_resign_streak,
    pass_ok,
    should_resign,
)
from ishi.engine.katago_process import KataGoProcess, KataGoQueryError
from ishi.engine.models import AnalysisResponse
from ishi.engine.queries import POSTGAME_VISITS, for_player, position_query, winrate_for
from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, index_to_point, point_to_index
from ishi.rules.game import GameState, legal_moves
from ishi.rules.scoring import Score, area_score

DEAD_OWNERSHIP = -0.8  # chain average, from the chain owner's perspective


@dataclass(frozen=True)
class BotTurn:
    point: Point | None  # None = pass
    resign: bool
    winrate: float  # bot's winrate before its move
    resign_streak: int


def summarize(resp: AnalysisResponse, player: Color) -> SearchSummary:
    infos = sorted(resp.moveInfos, key=lambda m: m.order)
    best = infos[0]
    pass_info = next((m for m in infos if m.move.lower() == "pass"), None)
    return SearchSummary(
        winrate=winrate_for(resp.rootInfo.winrate, player),
        best_move=best.move,
        best_lead=for_player(best.scoreLead, player),
        pass_lead=for_player(pass_info.scoreLead, player) if pass_info else None,
    )


async def bot_turn(
    engine: KataGoProcess,
    state: GameState,
    profile: BotProfile,
    rng: random.Random,
    *,
    resign_streak: int,
    qid: str,
    allow_resign: bool = True,
) -> BotTurn:
    resp = (
        await engine.analyze(
            position_query(
                qid, state, max_visits=BOT_VISITS, human_profile=profile.profile, ownership=True
            )
        )
    )[0]
    summary = summarize(resp, state.to_move)
    streak = next_resign_streak(resign_streak, summary.winrate, state.move_number)
    if allow_resign and should_resign(streak):
        return BotTurn(None, True, summary.winrate, streak)
    point: Point | None = None
    if not pass_ok(summary):
        policy = resp.humanPolicy or resp.policy
        if policy is None:
            raise KataGoQueryError(qid, "no humanPolicy in response")
        size = state.size
        legal = {point_to_index(p, size) for p in legal_moves(state)}
        idx = choose_index(policy, legal, profile, rng)
        point = None if idx is None else index_to_point(idx, size)
    if point is None and resp.ownership is not None:
        point = dame_fill(state, resp.ownership)
    return BotTurn(point, False, summary.winrate, streak)


def dame_fill(state: GameState, ownership_black: Sequence[float]) -> Point | None:
    """A neutral point (dame) the mover can fill safely, to play instead of passing (D-035).

    Area scoring counts an empty dame for nobody, but KataGo's score assumes it gets filled, so the
    bot fills dame before it passes. Dame = empty and owned by nobody once ownership-dead stones are
    removed; safe = legal and the new chain keeps 2+ liberties.
    """
    board = state.board
    territory = area_score(board, state.komi, dead_stones(board, ownership_black)).territory
    legal = legal_moves(state)
    for p in sorted(legal, key=lambda q: (q.y, q.x)):
        if board[p] is not None or territory[p] is not None:
            continue
        after, _ = board.place(p, state.to_move)
        group = after.group_at(p)
        if group is not None and len(group.liberties) >= 2:
            return p
    return None


def dead_stones(board: Board, ownership_black: Sequence[float]) -> set[Point]:
    """Chains whose average ownership says the other side owns them (ownership <= -0.8)."""
    dead: set[Point] = set()
    for g in board.groups():
        sign = 1.0 if g.color is Color.BLACK else -1.0
        own = sum(sign * ownership_black[point_to_index(p, board.size)] for p in g.stones)
        if own / g.size <= DEAD_OWNERSHIP:
            dead |= g.stones
    return dead


@dataclass(frozen=True)
class FinalScore:
    score: Score
    dead: set[Point]
    katago_lead: float  # KataGo's scoreLead for Black, for comparison
    katago_count: float  # KataGo's ownership counted point by point (Black minus White minus komi)


async def final_score(engine: KataGoProcess, state: GameState, *, qid: str) -> FinalScore:
    resp = (
        await engine.analyze(position_query(qid, state, max_visits=POSTGAME_VISITS, ownership=True))
    )[0]
    if resp.ownership is None:
        raise KataGoQueryError(qid, "no ownership in response")
    dead = dead_stones(state.board, resp.ownership)
    count = sum((o > 0) - (o < 0) for o in resp.ownership) - state.komi
    return FinalScore(
        area_score(state.board, state.komi, dead), dead, resp.rootInfo.scoreLead, count
    )
