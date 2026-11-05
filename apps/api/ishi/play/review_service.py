"""Background analysis and Why Engine review of full games (M4), backed by the database.

During a game every position is analyzed in the background (low priority), so when the game ends
only the last positions remain; then each learner move is classified and stored as a `Mistake`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session, select

from ishi.db.models import Analysis, Game, Mistake, User, utcnow
from ishi.db.session import get_engine
from ishi.engine.katago_process import EngineError, KataGoProcess
from ishi.engine.models import AnalysisResponse
from ishi.engine.queries import human_policy_query
from ishi.play.analysis import analyze_positions
from ishi.play.service import load_state
from ishi.rules.board import Color
from ishi.rules.game import GameState, new_game, play
from ishi.rules.sgf import to_sgf
from ishi.teacher.narrator import Completer
from ishi.why.detectors import UNEXPLAINED
from ishi.why.review import MoveReview, review_moves
from ishi.why.selector import (
    concept_unlocked,
    filter_hits,
    learner_rank,
    p_find,
    target_profile,
    uses_p_find,
)

log = logging.getLogger("ishi.review")

MOVE_INFOS_KEPT = 12
OWNERSHIP_DIGITS = 3
RETRY_SECONDS = 5.0


# -- rows <-> KataGo responses ------------------------------------------------------------


def _round(xs: list[float] | None) -> list[float] | None:
    return None if xs is None else [round(x, OWNERSHIP_DIGITS) for x in xs]


def analysis_row(game: Game, resp: AnalysisResponse, engine_version: str) -> Analysis:
    infos = sorted(resp.moveInfos, key=lambda m: m.order)[:MOVE_INFOS_KEPT]
    return Analysis(
        user_id=game.user_id,
        game_id=game.id,
        move_number=resp.turnNumber,
        visits=resp.rootInfo.visits,
        root=resp.rootInfo.model_dump(),
        move_infos=[
            {
                **m.model_dump(exclude_none=True, exclude={"ownership"}),
                "ownership": _round(m.ownership),
            }
            for m in infos
        ],
        ownership=_round(resp.ownership),
        engine_version=engine_version,
    )


def response_from_row(row: Analysis) -> AnalysisResponse:
    return AnalysisResponse.model_validate(
        {
            "id": f"{row.game_id}-{row.move_number}",
            "turnNumber": row.move_number,
            "moveInfos": row.move_infos,
            "rootInfo": row.root,
            "ownership": row.ownership,
        }
    )


def stored_analyses(session: Session, game: Game) -> dict[int, Analysis]:
    rows = session.exec(select(Analysis).where(Analysis.game_id == game.id)).all()
    return {r.move_number: r for r in rows}


# -- review -------------------------------------------------------------------------------


def seconds_since(moment: datetime) -> float:
    if moment.tzinfo is None:  # SQLite hands datetimes back without a zone; they are UTC
        moment = moment.replace(tzinfo=UTC)
    return (datetime.now(UTC) - moment).total_seconds()


def learner_color(game: Game) -> Color:
    return Color.BLACK if game.learner_color == "black" else Color.WHITE


def review_game(session: Session, game: Game, p_finds: dict[int, float | None]) -> list[Mistake]:
    """Classify every learner move and store the hits (replacing an earlier review)."""
    user = session.get(User, game.user_id)
    assert user is not None
    state = load_state(session, game)
    rows = stored_analyses(session, game)
    reviews = review_moves(
        state, {n: response_from_row(r) for n, r in rows.items()}, learner_color(game)
    )
    for old in session.exec(select(Mistake).where(Mistake.game_id == game.id)).all():
        session.delete(old)
    mistakes = []
    for c in filter_hits(reviews, user.belt, p_finds):
        mistakes.append(
            Mistake(
                user_id=game.user_id,
                game_id=game.id,
                move_number=c.review.number,
                points_lost=round(c.review.points_lost, 2),
                concept_id=c.hit.concept_id,
                secondary_concepts=c.hit.secondary,
                evidence=c.hit.to_json(state.size),
                p_find=c.p_find,
                eligible=c.eligible,
            )
        )
    session.add_all(mistakes)
    game.reviewed_at = utcnow()
    session.add(game)
    session.commit()
    log.info("reviewed game=%s mistakes=%d", game.id, len(mistakes))
    return mistakes


async def compute_p_finds(
    engine: KataGoProcess, state: GameState, reviews: list[MoveReview], belt: str, rank: float
) -> dict[int, float | None]:
    """p_find for every hit the learner's belt could be taught (needs Orange+, else skipped)."""
    if not uses_p_find(belt):
        return {}
    wanted = [
        r
        for r in reviews
        if r.hit and r.hit.concept_id != UNEXPLAINED and concept_unlocked(r.hit.concept_id, belt)
    ]
    if not wanted:
        return {}
    profile = target_profile(rank)
    query = human_policy_query("pfind", state, [r.number - 1 for r in wanted], profile)
    responses = {resp.turnNumber: resp for resp in await engine.analyze(query, timeout=60.0)}
    out: dict[int, float | None] = {}
    for r in wanted:
        resp = responses.get(r.number - 1)
        assert r.hit is not None
        if resp is not None and resp.humanPolicy is not None:
            out[r.number] = p_find(resp.humanPolicy, r.hit.correct_moves, state.size)
    return out


# -- background worker ----------------------------------------------------------------------


class AnalysisWorker:
    """One asyncio task: analyzes queued games position by position, reviews finished ones and
    prepares their lesson.

    Engine trouble never reaches the learner: the game is re-queued and retried later."""

    def __init__(
        self,
        db_path: Path,
        engine: Callable[[], KataGoProcess | None],
        teacher: Callable[[], Completer | None] = lambda: None,
        model: str = "",
    ) -> None:
        self._db_path = db_path
        self._engine = engine
        self._teacher = teacher
        self._model = model
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued: set[str] = set()
        self._task: asyncio.Task[None] | None = None
        self.idle = asyncio.Event()
        self.idle.set()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        with Session(get_engine(self._db_path)) as session:
            pending = session.exec(
                select(Game).where(Game.mode == "full", Game.reviewed_at == None)  # noqa: E711
            ).all()
            for g in pending:
                self.enqueue(g.id)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def enqueue(self, game_id: str) -> None:
        if game_id not in self._queued:
            self._queued.add(game_id)
            self.idle.clear()
            self._queue.put_nowait(game_id)

    async def _run(self) -> None:
        while True:
            game_id = await self._queue.get()
            self._queued.discard(game_id)
            try:
                done = await self.process(game_id)
            except EngineError as e:
                log.warning("analysis of game=%s failed (%s); retrying", game_id, e)
                done = False
            except Exception:
                log.exception("analysis of game=%s crashed", game_id)
                done = True
            if not done:
                await asyncio.sleep(RETRY_SECONDS)
                self.enqueue(game_id)
            if self._queue.empty():
                self.idle.set()

    async def process(self, game_id: str) -> bool:
        """Analyze what's missing; review if the game is over. False = try again later."""
        engine = self._engine()
        if engine is None or not engine.ready:
            return False
        with Session(get_engine(self._db_path)) as session:
            game = session.get(Game, game_id)
            if game is None or game.mode != "full" or game.reviewed_at is not None:
                return True
            state = load_state(session, game)
            have = stored_analyses(session, game)
            missing = [t for t in range(state.move_number + 1) if t not in have]
            finished = game.status == "finished"
            ended = game.updated_at  # set when the game finished: the lesson-ready clock
            user = session.get(User, game.user_id)
            assert user is not None
            belt, rank = user.belt, learner_rank(user.belt, user.rank_estimate)
        if missing:
            analyses = await analyze_positions(engine, state, missing, qid=f"{game_id}-bg")
            version = engine.version or ""
            with Session(get_engine(self._db_path)) as session:
                game = session.get(Game, game_id)
                assert game is not None
                have = stored_analyses(session, game)
                session.add_all(
                    analysis_row(game, a, version) for t, a in analyses.items() if t not in have
                )
                session.commit()
        if not finished:
            return True
        with Session(get_engine(self._db_path)) as session:
            game = session.get(Game, game_id)
            assert game is not None
            rows = stored_analyses(session, game)
            reviews = review_moves(
                state, {n: response_from_row(r) for n, r in rows.items()}, learner_color(game)
            )
        p_finds = await compute_p_finds(engine, state, reviews, belt, rank)
        with Session(get_engine(self._db_path)) as session:
            game = session.get(Game, game_id)
            assert game is not None
            review_game(session, game, p_finds)
            from ishi.play import lessons  # lessons builds on this module

            budget = (
                lessons.LESSON_READY_SECONDS - lessons.LESSON_MARGIN_SECONDS - seconds_since(ended)
            )
            await lessons.build_lesson(
                session, game, self._teacher(), self._model, budget, keep_late=True
            )
        return True


# -- unexplained-mistake export (05-why-engine: how the concept catalog grows) -------------


def export_unexplained(session: Session, out_dir: Path) -> list[Path]:
    """One folder per `unexplained` mistake, in the golden-case layout (position.sgf with the
    game up to the learner's move, both analyses) plus notes.md; returns the folders."""
    rows = session.exec(
        select(Mistake).where(Mistake.concept_id == UNEXPLAINED).order_by(Mistake.created_at)
    ).all()
    written = []
    for m in rows:
        game = session.get(Game, m.game_id)
        if game is None:
            continue
        analyses = stored_analyses(session, game)
        before, after = analyses.get(m.move_number - 1), analyses.get(m.move_number)
        if before is None or after is None:
            continue
        full = load_state(session, game)
        state = new_game(full.size, full.komi)
        for move in full.moves[: m.move_number]:
            state = play(state, move.point)
        d = out_dir / f"{game.id[:8]}_m{m.move_number:03d}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "position.sgf").write_text(to_sgf(state) + "\n", encoding="utf-8")
        for name, row in (("analysis_before.json", before), ("analysis_after.json", after)):
            data = response_from_row(row).model_dump(exclude_none=True)
            (d / name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        best = ", ".join(m.evidence.get("correct_moves", []))
        played = m.evidence.get("evidence", {}).get("played_move", "?")
        (d / "notes.md").write_text(
            f"unexplained: move {m.move_number} {played} lost {m.points_lost:.1f} points; "
            f"KataGo's best: {best}. Game {game.id}.\n",
            encoding="utf-8",
        )
        written.append(d)
    return written
