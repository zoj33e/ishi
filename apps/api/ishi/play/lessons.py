"""Post-game lessons (M5): pick the one lesson of a game, narrate it, run the retry and hint ladder,
and turn it into a Shape Gym puzzle when the learner is done.

Selection follows 05-why-engine (rank-aware mistake, else praise, else clean game); narration
follows 06-teacher-llm (template always, Claude when enabled, validator in between, cached).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from sqlmodel import Session, col, select

from ishi.db.models import Game, Lesson, Mistake, NarrationCache, Puzzle, User, utcnow
from ishi.play.review_service import learner_color, response_from_row, stored_analyses
from ishi.play.service import load_state
from ishi.rules.board import Color
from ishi.rules.coords import gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, Legality, check_move, new_game, play
from ishi.teacher.narration import Narration
from ishi.teacher.narrator import (
    Completer,
    NarrationResult,
    cache_key,
    finish_late,
    narrate,
    uses_llm,
)
from ishi.why.context import MoveContext
from ishi.why.fact_package import (
    FactPackage,
    clean_package,
    learner_info,
    mistake_package,
    praise_package,
)
from ishi.why.review import MoveReview, review_moves
from ishi.why.selector import filter_hits, find_praise, pick_mistake

log = logging.getLogger("ishi.lessons")

RECENT_GAMES = 10  # weakest concepts: most frequent hits in the last 10 games
SOLUTION_PLIES = 6
HINT_QUESTION, HINT_AREA, HINT_SOLUTION = 1, 2, 3
WRONG_BEFORE_SOLUTION = 2  # 02-curriculum: after two failed tries, show the move and the line

Locale = Literal["th", "en"]


# -- choosing the lesson -------------------------------------------------------------------


def _locale(user: User) -> Locale:
    return "en" if user.locale == "en" else "th"


def recent_concepts(session: Session, user_id: str) -> list[str]:
    games = session.exec(
        select(Game.id)
        .where(Game.user_id == user_id, Game.reviewed_at != None)  # noqa: E711
        .order_by(col(Game.reviewed_at).desc())
        .limit(RECENT_GAMES)
    ).all()
    rows = session.exec(select(Mistake.concept_id).where(col(Mistake.game_id).in_(games))).all()
    return list(rows)


def last_taught(session: Session, user_id: str) -> str | None:
    last = session.exec(
        select(Lesson)
        .where(Lesson.user_id == user_id, Lesson.lesson_type == "mistake")
        .order_by(col(Lesson.created_at).desc())
    ).first()
    return last.concept_id if last else None


def concept_is_new(session: Session, user_id: str, concept: str) -> bool:
    taught = session.exec(
        select(Lesson.id).where(Lesson.user_id == user_id, Lesson.concept_id == concept)
    ).first()
    return taught is None


def solution_line(ctx: MoveContext, first: str) -> list[str]:
    """KataGo's line starting with the correct move, as "B E5", "W F4", ... (at most 6 plies)."""
    info = next((m for m in ctx.before.moveInfos if m.move.upper() == first.upper()), None)
    pv = (info.pv if info and info.pv else None) or [first]
    color, out = ctx.learner, []
    for m in pv[:SOLUTION_PLIES]:
        out.append(f"{color.value} {m.upper() if m.lower() != 'pass' else 'pass'}")
        color = color.opponent
    return out


def game_reviews(session: Session, game: Game) -> list[MoveReview]:
    state = load_state(session, game)
    rows = stored_analyses(session, game)
    return review_moves(
        state, {n: response_from_row(r) for n, r in rows.items()}, learner_color(game)
    )


def choose_lesson(
    session: Session, game: Game, user: User, reviews: list[MoveReview], locale: Locale
) -> tuple[FactPackage, Mistake | None, list[str]]:
    """The game's one lesson as a FactPackage, its Mistake row and the solution line."""
    mistakes = {
        m.move_number: m
        for m in session.exec(select(Mistake).where(Mistake.game_id == game.id)).all()
    }
    p_finds = {n: m.p_find for n, m in mistakes.items()}
    learner = learner_info(user.belt, user.rank_estimate)
    chosen = pick_mistake(
        filter_hits(reviews, user.belt, p_finds),
        recent_concepts(session, user.id),
        last_taught(session, user.id),
    )
    if chosen is not None:
        r, hit = chosen.review, chosen.hit
        pkg = mistake_package(
            r,
            hit,
            locale=locale,
            learner=learner,
            concept_is_new=concept_is_new(session, user.id, hit.concept_id),
        )
        return pkg, mistakes.get(r.number), solution_line(r.ctx, hit.correct_moves[0])
    praise = find_praise(reviews)
    if praise is not None:
        return praise_package(praise, locale=locale, learner=learner), None, []
    pkg = clean_package(
        locale=locale, learner=learner, size=game.board_size, color=learner_color(game)
    )
    return pkg, None, []


# -- narration with cache --------------------------------------------------------------------


async def narrate_cached(
    session: Session,
    user_id: str,
    pkg: FactPackage,
    llm: Completer | None,
    model: str,
    budget: float | None = None,
    keep_late: bool = False,
) -> NarrationResult:
    if llm is not None and uses_llm(pkg):
        key = cache_key(pkg)
        hit = session.exec(
            select(NarrationCache).where(
                NarrationCache.user_id == user_id, NarrationCache.key == key
            )
        ).first()
        if hit is not None:
            return NarrationResult(Narration.model_validate(hit.narration), "llm")
        result = await narrate(pkg, llm, budget, keep_late)
        if result.source == "llm":
            _cache(session, user_id, key, result.narration, model)
        return result
    return await narrate(pkg, None)


def _cache(session: Session, user_id: str, key: str, narration: Narration, model: str) -> None:
    session.add(
        NarrationCache(user_id=user_id, key=key, narration=narration.model_dump(), model=model)
    )


async def build_lesson(
    session: Session,
    game: Game,
    llm: Completer | None,
    model: str = "",
    budget: float | None = None,
    keep_late: bool = False,
) -> Lesson:
    """Create (or return) the lesson of a reviewed game; Claude gets at most `budget` seconds.

    With `keep_late`, the template lesson is saved when the budget runs out (the lesson is ready)
    and Claude's narration replaces it when it arrives, if valid and the lesson is still unseen."""
    existing = session.exec(select(Lesson).where(Lesson.game_id == game.id)).first()
    if existing is not None:
        return existing
    user = session.get(User, game.user_id)
    assert user is not None
    reviews = game_reviews(session, game)
    pkg, mistake, line = choose_lesson(session, game, user, reviews, _locale(user))
    result = await narrate_cached(session, user.id, pkg, llm, model, budget, keep_late)
    lesson = Lesson(
        user_id=user.id,
        game_id=game.id,
        mistake_id=mistake.id if mistake else None,
        lesson_type=pkg.lesson_type,
        concept_id=pkg.concept_id,
        move_number=pkg.move_number,
        fact_package=pkg.model_dump(),
        narration=result.narration.model_dump(),
        narration_source=result.source,
        llm_reject_reason=result.reject_reason,
        solution_line=line,
    )
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    log.info(
        "lesson game=%s type=%s concept=%s source=%s reject=%s",
        game.id,
        lesson.lesson_type,
        lesson.concept_id,
        lesson.narration_source,
        lesson.llm_reject_reason,
    )
    if result.late is not None:
        await _upgrade_late(session, lesson, pkg, result.late, model)
    return lesson


async def _upgrade_late(
    session: Session,
    lesson: Lesson,
    pkg: FactPackage,
    late: asyncio.Future[NarrationResult],
    model: str,
) -> None:
    result = await finish_late(pkg, late)
    session.refresh(lesson)
    if result.source == "llm":
        _cache(session, lesson.user_id, cache_key(pkg), result.narration, model)
        if lesson.viewed_at is None:
            lesson.narration = result.narration.model_dump()
            lesson.narration_source = "llm"
            lesson.llm_reject_reason = None
    else:
        lesson.llm_reject_reason = f"late:{result.reject_reason}"
    session.add(lesson)
    session.commit()
    log.info("lesson game=%s late narration %s", lesson.game_id, lesson.narration_source)


# 10-roadmap M5: the lesson is ready < 4 s after the game ends. The worker gives Claude what is
# left of that after the review; the learner waits on a language switch, so that gets 3 s.
LESSON_READY_SECONDS = 4.0
LESSON_MARGIN_SECONDS = 0.3
RELOCALIZE_BUDGET = 3.0


async def relocalize(
    session: Session, lesson: Lesson, locale: Locale, llm: Completer | None, model: str = ""
) -> Lesson:
    """The learner switched language: same facts, narration in the new locale."""
    pkg = FactPackage.model_validate(lesson.fact_package)
    if pkg.locale == locale:
        return lesson
    pkg = pkg.model_copy(update={"locale": locale})
    result = await narrate_cached(session, lesson.user_id, pkg, llm, model, RELOCALIZE_BUDGET)
    lesson.fact_package = pkg.model_dump()
    lesson.narration = result.narration.model_dump()
    lesson.narration_source = result.source
    lesson.llm_reject_reason = result.reject_reason
    lesson.updated_at = utcnow()
    session.add(lesson)
    session.commit()
    return lesson


# -- the lesson screen: position, retry, hints, done --------------------------------------


def package(lesson: Lesson) -> FactPackage:
    return FactPackage.model_validate(lesson.fact_package)


def lesson_position(session: Session, game: Game, lesson: Lesson) -> GameState:
    """The board the lesson is about: before the learner's move (the whole game for a clean one)."""
    full = load_state(session, game)
    if lesson.move_number is None:
        return full
    state = new_game(full.size, full.komi)
    for move in full.moves[: lesson.move_number - 1]:
        state = play(state, move.point)
    return state


SMALL_POINTS, BIG_POINTS = 3.0, 8.0  # 09-ui-ux: points lost shown only as small / medium / big


def severity(points_lost: float | None) -> Literal["small", "medium", "big"] | None:
    if points_lost is None:
        return None
    if points_lost < SMALL_POINTS:
        return "small"
    return "medium" if points_lost < BIG_POINTS else "big"


def pending_lesson(session: Session, user_id: str) -> Lesson | None:
    """The newest lesson the learner hasn't finished (for the home screen)."""
    return session.exec(
        select(Lesson)
        .where(Lesson.user_id == user_id, Lesson.done_at == None)  # noqa: E711
        .order_by(col(Lesson.created_at).desc())
    ).first()


def line_frames(state: GameState, line: list[str]) -> list[GameState]:
    """The positions after each ply of a "B E5"-style line (stops at the first illegal move)."""
    frames = []
    for ply in line:
        move = ply.split()[-1]
        point = None if move.lower() == "pass" else gtp_to_point(move, state.size)
        if check_move(state, point) is not Legality.OK:
            break
        state = play(state, point)
        frames.append(state)
    return frames


def focus_point(lesson: Lesson) -> str | None:
    """Center of the level-2 area hint: the first correct move."""
    moves = package(lesson).correct_moves
    return moves[0] if moves else None


def can_retry(lesson: Lesson) -> bool:
    return lesson.lesson_type == "mistake" and lesson.retry_result is None


def retry(session: Session, lesson: Lesson, point: str) -> bool:
    """Grade a retry move. Wrong answers climb the hint ladder: the first shows the guiding
    question, the second shows the solution. Returns whether the move was correct."""
    pkg = package(lesson)
    correct = point.upper() in {m.upper() for m in pkg.correct_moves}
    lesson.attempts += 1
    if correct:
        clean = lesson.attempts == 1 and lesson.hint_level == 0
        lesson.retry_result = "solved_first" if clean else "solved_hint"
    elif lesson.attempts >= WRONG_BEFORE_SOLUTION:
        lesson.hint_level = HINT_SOLUTION
        lesson.retry_result = "failed"
    else:
        lesson.hint_level = max(lesson.hint_level, HINT_QUESTION)
    lesson.updated_at = utcnow()
    session.add(lesson)
    session.commit()
    return correct


def next_hint(session: Session, lesson: Lesson) -> int:
    """The learner asked for a hint: one level up (question -> area -> solution)."""
    lesson.hint_level = min(lesson.hint_level + 1, HINT_SOLUTION)
    if lesson.hint_level == HINT_SOLUTION and lesson.retry_result is None:
        lesson.retry_result = "failed"
    lesson.updated_at = utcnow()
    session.add(lesson)
    session.commit()
    return lesson.hint_level


def mark_viewed(session: Session, lesson: Lesson) -> None:
    if lesson.viewed_at is None:
        lesson.viewed_at = utcnow()
        session.add(lesson)
        session.commit()


def finish_lesson(session: Session, game: Game, lesson: Lesson) -> bool:
    """Mark the lesson done; a mistake lesson becomes a Shape Gym puzzle (once).
    Returns whether a puzzle exists for it."""
    if lesson.done_at is None:
        lesson.done_at = utcnow()
        session.add(lesson)
    added = False
    if lesson.lesson_type == "mistake":
        exists = session.exec(select(Puzzle.id).where(Puzzle.origin_lesson_id == lesson.id)).first()
        if exists is None:
            session.add(puzzle_from_lesson(session, game, lesson))
        added = True
    session.commit()
    return added


def puzzle_from_lesson(session: Session, game: Game, lesson: Lesson) -> Puzzle:
    state = lesson_position(session, game, lesson)
    pkg = package(lesson)
    size = state.size
    return Puzzle(
        user_id=lesson.user_id,
        source="own_mistake",
        concept_id=pkg.concept_id or "",
        board_size=size,
        setup={
            "black": [point_to_gtp(p, size) for p in state.board.stones(Color.BLACK)],
            "white": [point_to_gtp(p, size) for p in state.board.stones(Color.WHITE)],
            "to_move": "black" if state.to_move is Color.BLACK else "white",
            "komi": state.komi,
            "ko_point": point_to_gtp(state.ko_point, size) if state.ko_point else None,
            "rules": game.rules,
        },
        correct_moves=list(pkg.correct_moves),
        solution_line=list(lesson.solution_line),
        origin_lesson_id=lesson.id,
    )
