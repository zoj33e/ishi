"""Capture games, stages and the Yellow exam backed by the database (I/O lives here).

Full 9x9 games against the HumanSL bot live in `ishi.play.full_service`."""

from __future__ import annotations

import logging
import random

from sqlmodel import Session, col, select

from ishi.bots.capture_bot import CaptureBot, capture_over, capture_result, capture_winner
from ishi.db.models import Exam, Game, LessonProgress, Move, User, utcnow
from ishi.play.progression import (
    EXAM_STAGE,
    ExamRecord,
    PlayedGame,
    Stage,
    StageStatus,
    current_stage,
    exam_available,
    exam_outcome,
)
from ishi.rules.board import Color
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, new_game, play
from ishi.rules.sgf import to_sgf
from ishi.school.content import load_lessons

log = logging.getLogger("ishi.play")

LEARNER = Color.BLACK  # D-024/D-030: the learner always plays Black


# -- history -----------------------------------------------------------------------------


def capture_history(session: Session, user: User) -> list[Game]:
    """Finished non-exam capture games, oldest first."""
    return list(
        session.exec(
            select(Game)
            .where(Game.user_id == user.id, Game.mode == "capture", Game.status == "finished")
            .where(col(Game.exam_id).is_(None))
            .order_by(col(Game.created_at))
        )
    )


def stage_status(session: Session, user: User) -> StageStatus:
    games = capture_history(session, user)
    return current_stage(
        [PlayedGame(int(g.bot_params.get("stage", 1)), bool(g.learner_won)) for g in games]
    )


def lessons_done(session: Session, user: User) -> bool:
    done = set(
        session.exec(
            select(LessonProgress.lesson_id).where(
                LessonProgress.user_id == user.id, LessonProgress.status == "done"
            )
        )
    )
    return all(lesson.id in done for lesson in load_lessons())


def user_exams(session: Session, user: User) -> list[Exam]:
    return list(
        session.exec(
            select(Exam)
            .where(Exam.user_id == user.id, Exam.belt_target == "yellow")
            .order_by(col(Exam.created_at))
        )
    )


def active_exam(session: Session, user: User) -> Exam | None:
    return next((e for e in user_exams(session, user) if e.status == "in_progress"), None)


def can_take_exam(session: Session, user: User) -> bool:
    games = capture_history(session, user)
    records = [
        ExamRecord(
            e.status,
            sum(1 for g in games if e.status != "in_progress" and g.created_at > e.updated_at),
        )
        for e in user_exams(session, user)
    ]
    return exam_available(user.belt, lessons_done(session, user), len(games), records)


# -- games -------------------------------------------------------------------------------


def start_game(session: Session, user: User, exam: Exam | None = None) -> Game:
    stage: Stage = EXAM_STAGE if exam else stage_status(session, user).stage
    game = Game(
        user_id=user.id,
        mode="capture",
        board_size=stage.board_size,
        rules={"type": "capture", "target": stage.target},
        komi=0,
        learner_color="black",
        bot_kind="capture_bot",
        bot_params={"level": stage.level, "target": stage.target, "stage": stage.number},
        exam_id=exam.id if exam else None,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def game_moves(session: Session, game: Game) -> list[Move]:
    return list(
        session.exec(select(Move).where(Move.game_id == game.id).order_by(col(Move.number)))
    )


def load_state(session: Session, game: Game) -> GameState:
    state = new_game(game.board_size, game.komi)
    for m in game_moves(session, game):
        state = play(state, gtp_to_point(m.point or "pass", game.board_size))
    return state


def target(game: Game) -> int:
    return int(game.bot_params.get("target", 1))


def record_move(
    session: Session,
    game: Game,
    before: GameState,
    point: Point | None,
    *,
    bot_winrate: float | None = None,
) -> GameState:
    after = play(before, point)
    last = after.last_move
    assert last is not None
    session.add(
        Move(
            user_id=game.user_id,
            game_id=game.id,
            number=after.move_number,
            color="black" if last.color is Color.BLACK else "white",
            point=None if point is None else point_to_gtp(point, game.board_size),
            captures=len(last.captured),
            by_learner=last.color is LEARNER,
            bot_winrate=bot_winrate,
        )
    )
    return after


def play_learner_move(
    session: Session, game: Game, state: GameState, point: Point | None, rng: random.Random
) -> tuple[GameState, str | None]:
    """Apply a legal learner move and the bot's reply. Returns (state, bot move GTP or None)."""
    state = record_move(session, game, state, point)
    bot_gtp: str | None = None
    if not capture_over(state, target(game)):
        bot = CaptureBot(int(game.bot_params.get("level", 1)), target(game), rng=rng)
        bot_point = bot.choose(state)
        log.debug("capture bot game=%s level=%s move=%s", game.id, bot.level, bot_point)
        state = record_move(session, game, state, bot_point)
        bot_gtp = point_to_gtp(bot_point, game.board_size)
    if capture_over(state, target(game)):
        won = capture_winner(state, target(game)) is LEARNER
        finish(session, game, state, capture_result(state, target(game)), learner_won=won)
    game.updated_at = utcnow()
    session.add(game)
    session.commit()
    return state, bot_gtp


def finish(
    session: Session, game: Game, state: GameState, result: str, *, learner_won: bool
) -> None:
    """A draw is recorded as not won (it neither extends a streak nor counts as an exam win)."""
    if game.status == "finished":
        return
    game.status = "finished"
    game.result = result
    game.learner_won = learner_won
    game.sgf = to_sgf(state, result=result)
    game.updated_at = utcnow()
    session.add(game)
    if game.exam_id:
        _update_exam(session, game)


def resign(session: Session, game: Game, state: GameState) -> None:
    """The learner (Black) gives up."""
    finish(session, game, state, "W+R", learner_won=False)
    session.commit()


def _update_exam(session: Session, game: Game) -> None:
    exam = session.get(Exam, game.exam_id)
    if exam is None or exam.status != "in_progress":
        return
    if game.learner_won:
        exam.games_won += 1
    else:
        exam.games_lost += 1
    exam.status = exam_outcome(exam.games_won, exam.games_lost)
    exam.updated_at = utcnow()
    session.add(exam)
    if exam.status == "passed":
        user = session.get(User, exam.user_id)
        assert user is not None
        user.belt = "yellow"
        user.updated_at = utcnow()
        session.add(user)


def start_exam(session: Session, user: User) -> Exam:
    exam = Exam(user_id=user.id, belt_target="yellow")
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return exam
