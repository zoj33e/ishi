"""Full 9x9 games against the HumanSL bot (M3), backed by the database and KataGo."""

from __future__ import annotations

import logging
import random

from sqlmodel import Session

from ishi.bots.humansl_bot import BotProfile, next_resign_streak, profile_for, rank_label
from ishi.config import get_settings
from ishi.db.models import Game, Move, User, utcnow
from ishi.engine.katago_process import KataGoProcess
from ishi.play.full_game import bot_turn, final_score
from ishi.play.service import LEARNER, finish, game_moves, record_move
from ishi.rules.coords import Point, point_to_gtp
from ishi.rules.game import GameState, play
from ishi.rules.scoring import Score

log = logging.getLogger("ishi.play")

FULL_SIZE = 9
FULL_KOMI = 7.0


def full_games_unlocked(user: User) -> bool:
    """D-030: real 9x9 games open after the Yellow belt (or with ISHI_DEV_UNLOCK_ALL)."""
    return user.belt != "white" or get_settings().dev_unlock_all


def start_full_game(session: Session, user: User, rank: float, exam_id: str | None = None) -> Game:
    p = profile_for(rank)
    game = Game(
        user_id=user.id,
        mode="full",
        board_size=FULL_SIZE,
        rules={"type": "area", "ko": "simple", "suicide": False},
        komi=FULL_KOMI,
        learner_color="black",
        bot_kind="humansl",
        bot_rank=p.rank,
        bot_params={
            "profile": p.profile,
            "temperature": p.temperature,
            "blunder": p.blunder,
            "label": rank_label(p.rank),
        },
        exam_id=exam_id,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def bot_profile(game: Game) -> BotProfile:
    bp = game.bot_params
    return BotProfile(
        game.bot_rank or 30.0, bp["profile"], float(bp["temperature"]), float(bp["blunder"])
    )


def resign_streak(moves: list[Move]) -> int:
    """Replays the resign rule over the bot's recorded winrates."""
    streak = 0
    for m in moves:
        if not m.by_learner and m.bot_winrate is not None:
            streak = next_resign_streak(streak, m.bot_winrate, m.number - 1)
    return streak


async def play_full_move(
    session: Session,
    game: Game,
    state: GameState,
    point: Point | None,
    engine: KataGoProcess,
    rng: random.Random,
) -> tuple[GameState, str | None]:
    """Learner move, then the bot's answer (or its resignation), then scoring after two passes.

    The bot is asked before anything is written, so an engine failure leaves the game unchanged.
    """
    trial = play(state, point)
    bot_gtp: str | None = None
    if trial.is_over:
        fs = await final_score(engine, trial, qid=f"{game.id}-final")
        state = record_move(session, game, state, point)
        _finish_scored(session, game, state, fs.score, fs.dead, fs.katago_lead)
    else:
        turn = await bot_turn(
            engine,
            trial,
            bot_profile(game),
            rng,
            resign_streak=resign_streak(game_moves(session, game)),
            qid=f"{game.id}-m{trial.move_number}",
        )
        state = record_move(session, game, state, point)
        if turn.resign:
            finish(session, game, state, "B+R", learner_won=True)
            bot_gtp = "resign"
        else:
            state = record_move(session, game, state, turn.point, bot_winrate=turn.winrate)
            bot_gtp = point_to_gtp(turn.point, game.board_size)
            log.debug("humansl bot game=%s move=%s winrate=%.3f", game.id, bot_gtp, turn.winrate)
            if state.is_over:
                fs = await final_score(engine, state, qid=f"{game.id}-final")
                _finish_scored(session, game, state, fs.score, fs.dead, fs.katago_lead)
    game.updated_at = utcnow()
    session.add(game)
    session.commit()
    return state, bot_gtp


def _finish_scored(
    session: Session,
    game: Game,
    state: GameState,
    score: Score,
    dead: set[Point],
    katago_lead: float,
) -> None:
    size = game.board_size
    game.final_score = {
        "black_area": score.black_area,
        "white_area": score.white_area,
        "komi": score.komi,
        "dead": sorted(point_to_gtp(p, size) for p in dead),
        "katago_lead": round(katago_lead, 2),
    }
    finish(session, game, state, score.result, learner_won=score.winner is LEARNER)
