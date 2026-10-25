"""Bot-vs-bot 9x9 games through KataGo (calibration and the M3 score check)."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from ishi.bots.humansl_bot import BotProfile
from ishi.engine.katago_process import KataGoProcess
from ishi.play.full_game import bot_turn, final_score
from ishi.rules.board import Color
from ishi.rules.game import GameState, new_game, play

MAX_MOVES = 200


@dataclass
class SelfPlayResult:
    winner: Color | None
    result: str  # "B+3.0", "W+R", "0"
    moves: int
    move_seconds: list[float] = field(default_factory=list)
    our_margin: float | None = None  # Black's area margin after removing dead stones
    katago_lead: float | None = None  # KataGo's scoreLead for Black at the end
    katago_count: float | None = None  # KataGo's ownership counted point by point
    state: GameState | None = None


async def self_play(
    engine: KataGoProcess,
    black: BotProfile,
    white: BotProfile,
    rng: random.Random,
    *,
    gid: str,
    size: int = 9,
    komi: float = 7,
    allow_resign: bool = True,
) -> SelfPlayResult:
    state = new_game(size, komi)
    streak = {Color.BLACK: 0, Color.WHITE: 0}
    times: list[float] = []
    while not state.is_over and state.move_number < MAX_MOVES:
        mover = state.to_move
        t0 = time.perf_counter()
        turn = await bot_turn(
            engine,
            state,
            black if mover is Color.BLACK else white,
            rng,
            resign_streak=streak[mover],
            qid=f"{gid}-m{state.move_number}",
            allow_resign=allow_resign,
        )
        times.append(time.perf_counter() - t0)
        streak[mover] = turn.resign_streak
        if turn.resign:
            winner = mover.opponent
            return SelfPlayResult(
                winner,
                f"{'B' if winner is Color.BLACK else 'W'}+R",
                state.move_number,
                times,
                state=state,
            )
        state = play(state, turn.point)
    fs = await final_score(engine, state, qid=f"{gid}-final")
    return SelfPlayResult(
        fs.score.winner,
        fs.score.result,
        state.move_number,
        times,
        our_margin=fs.score.margin,
        katago_lead=fs.katago_lead,
        katago_count=fs.katago_count,
        state=state,
    )
