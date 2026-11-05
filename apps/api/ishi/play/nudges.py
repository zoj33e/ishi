"""Socratic nudges (M7, 06-teacher-llm "Nudge rules"): before a big teachable mistake is played,
the teacher asks a question instead.

Trigger: the ghost move loses >= max(4, 2 x the learner's median pointsLost over their last 5
reviewed games), a detector fires, the concept is unlocked and the rank filter passes. At most 2
per game, never in exams or capture games, and only when the learner hasn't turned them off.

Speed (p95 < 1.5 s): the position the learner is thinking about is analyzed in the background as
soon as the bot has moved (`LiveAnalysis`), so a preview only needs one short query on the position
after the ghost move - and none at all when the ghost move is clearly fine.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import statistics
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal, get_args

from sqlmodel import Session, col, select

from ishi.db.models import Analysis, Game, Move, User
from ishi.engine.katago_process import EngineError, KataGoProcess
from ishi.engine.models import AnalysisQuery, AnalysisResponse
from ishi.engine.queries import best_lead, for_player, game_analysis_query, human_policy_query
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, play
from ishi.teacher.narration import Narration
from ishi.teacher.templates import render
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.detectors import classify
from ishi.why.fact_package import learner_info, nudge_package
from ishi.why.review import MoveReview
from ishi.why.selector import filter_hits, learner_rank, p_find, target_profile, uses_p_find

Locale = Literal["th", "en"]
LOCALES: tuple[Locale, ...] = get_args(Locale)

log = logging.getLogger("ishi.nudges")

NUDGES_PER_GAME = 2
HINT_LEVELS = 2  # after a nudge: question + marks, then the area
MIN_THRESHOLD = 4.0  # points
RECENT_GAMES = 5
LIVE_VISITS = 200  # 04-katago: live position analysis
LIVE_PRIORITY = 10  # ahead of the post-game review (-10)
LIVE_WAIT = 1.2  # seconds a preview waits for the background analysis of the position
AFTER_VISITS = 100  # the position after the ghost move (points lost + ownership)
FAST_SKIP = 0.5  # skip the "after" query when KataGo already rates the move this close
MAX_CACHED = 16


# -- who gets nudges --------------------------------------------------------------------------


def nudges_on(game: Game, user: User) -> bool:
    """Full games outside exams, while the learner keeps nudges switched on (settings)."""
    return (
        game.mode == "full"
        and game.exam_id is None
        and game.status == "active"
        and bool(user.settings.get("nudges", True))
    )


def nudges_left(game: Game, user: User) -> int:
    return max(0, NUDGES_PER_GAME - game.nudges_used) if nudges_on(game, user) else 0


def threshold(recent_losses: list[float]) -> float:
    """max(4, 2 x the median pointsLost of the learner's recent moves)."""
    median = statistics.median(recent_losses) if recent_losses else 0.0
    return max(MIN_THRESHOLD, 2 * median)


def recent_losses(session: Session, user_id: str, games: int = RECENT_GAMES) -> list[float]:
    """pointsLost of every learner move in the learner's last reviewed full games."""
    rows = session.exec(
        select(Game.id, Game.learner_color)
        .where(Game.user_id == user_id, Game.mode == "full", col(Game.reviewed_at).isnot(None))
        .order_by(col(Game.reviewed_at).desc())
        .limit(games)
    ).all()
    out: list[float] = []
    for game_id, color in rows:
        learner = 0 if color == "black" else 1  # black moves at odd numbers
        found = session.exec(
            select(Analysis.move_number, Analysis.root, Analysis.move_infos).where(
                Analysis.game_id == game_id
            )
        ).all()
        by_n = {n: (root, infos) for n, root, infos in found}
        for n in by_n:
            if n == 0 or (n - 1) % 2 != learner or n - 1 not in by_n:
                continue
            infos = by_n[n - 1][1]
            if not infos:
                continue
            sign = 1.0 if learner == 0 else -1.0
            top = min(infos, key=lambda m: m.get("order", 0))
            lost = sign * (top["scoreLead"] - by_n[n][0]["scoreLead"])
            out.append(max(0.0, lost))
    return out


def game_threshold(session: Session, game: Game) -> float:
    """Fixed for the whole game (computed on the first preview)."""
    params = dict(game.bot_params)
    if "nudge_threshold" not in params:
        params["nudge_threshold"] = round(threshold(recent_losses(session, game.user_id)), 2)
        game.bot_params = params
        session.add(game)
        session.commit()
    return float(params["nudge_threshold"])


# -- live analysis of the current position ----------------------------------------------------


def live_query(qid: str, state: GameState, *, max_visits: int = LIVE_VISITS) -> AnalysisQuery:
    """The position now, with ownership (detectors read it), ahead of background work."""
    q = game_analysis_query(qid, state, [len(state.moves)], max_visits=max_visits)
    q.priority = LIVE_PRIORITY
    return q


class LiveAnalysis:
    """Background analysis of each game's current position, started right after the bot moves."""

    def __init__(self, engine: Callable[[], KataGoProcess | None]) -> None:
        self._engine = engine
        self._tasks: dict[tuple[str, int], asyncio.Task[AnalysisResponse]] = {}
        self._previews = 0

    @property
    def busy(self) -> bool:
        """A learner is waiting on the engine: a preview, or the position they're looking at."""
        return self._previews > 0 or any(not t.done() for t in self._tasks.values())

    async def wait_quiet(self, poll: float = 0.05) -> None:
        """Background work yields to the learner (the post-game review would slow nudges)."""
        while self.busy:
            await asyncio.sleep(poll)

    @contextlib.contextmanager
    def previewing(self) -> Iterator[None]:
        self._previews += 1
        try:
            yield
        finally:
            self._previews -= 1

    def warm(self, game_id: str, state: GameState) -> None:
        engine = self._engine()
        key = (game_id, len(state.moves))
        if engine is None or key in self._tasks:
            return
        for old in [k for k in self._tasks if k[0] == game_id]:
            self._tasks.pop(old).cancel()
        while len(self._tasks) >= MAX_CACHED:
            self._tasks.pop(next(iter(self._tasks))).cancel()
        qid = f"{game_id}-live{key[1]}"
        self._tasks[key] = asyncio.ensure_future(self._analyze(engine, live_query(qid, state)))

    @staticmethod
    async def _analyze(engine: KataGoProcess, query: AnalysisQuery) -> AnalysisResponse:
        (resp,) = await engine.analyze(query, timeout=10)
        return resp

    async def get(
        self, game_id: str, state: GameState, wait: float = LIVE_WAIT
    ) -> AnalysisResponse:
        self.warm(game_id, state)
        task = self._tasks.get((game_id, len(state.moves)))
        if task is None:
            raise EngineError("no engine")
        return await asyncio.wait_for(asyncio.shield(task), wait)

    async def close(self) -> None:
        for t in self._tasks.values():
            t.cancel()
        for t in self._tasks.values():
            with contextlib.suppress(BaseException):
                await t
        self._tasks.clear()


# -- the decision -----------------------------------------------------------------------------


def quick_loss(before: AnalysisResponse, move: str, mover: Any) -> float | None:
    """KataGo's own estimate for a move it already searched, else None."""
    for m in before.moveInfos:
        if m.move == move and m.visits >= 10:
            return best_lead(before, mover) - for_player(m.scoreLead, mover)
    return None


def decide(
    ctx: MoveContext, number: int, belt: str, limit: float, pf: float | None
) -> tuple[MoveReview, ConceptHit] | None:
    """A nudge-worthy mistake: big enough, explained by a detector, and teachable now."""
    if ctx.points_lost < limit:
        return None
    hit = classify(ctx)
    if hit is None:
        return None
    review = MoveReview(number, ctx.gtp(ctx.move), ctx.points_lost, hit, ctx)
    [cand] = filter_hits([review], belt, {number: pf})
    return (review, hit) if cand.eligible else None


def focus_area(correct: list[str], size: int) -> str | None:
    """Center of the hint's 3x3 area: a point next to the answer (toward the board's center),
    so the answer isn't simply the middle of the highlight."""
    if not correct:
        return None
    p = gtp_to_point(correct[0], size)
    if p is None:
        return None
    mid = (size - 1) / 2
    dx = 0 if p.x == mid else (1 if p.x < mid else -1)
    dy = 0 if p.y == mid else (1 if p.y < mid else -1)
    if dx == dy == 0:  # the answer is the center point itself
        dx = 1
    return point_to_gtp(Point(p.x + dx, p.y + dy), size)


@dataclass(frozen=True)
class Nudge:
    move_number: int  # the learner's move this nudge is about (1-based)
    point: str  # the ghost move
    concept_id: str
    narrations: dict[str, Narration]  # both languages: the learner may switch mid-game
    marks: list[str]  # hint 1: the stones in question
    focus: str | None  # hint 2: center of the highlighted area

    def narration(self, locale: Locale) -> Narration:
        return self.narrations[locale]

    def to_json(self) -> dict[str, Any]:
        return {
            "move_number": self.move_number,
            "point": self.point,
            "concept_id": self.concept_id,
            "narrations": {k: v.model_dump() for k, v in self.narrations.items()},
            "marks": self.marks,
            "focus": self.focus,
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> Nudge:
        return cls(
            d["move_number"],
            d["point"],
            d["concept_id"],
            {k: Narration.model_validate(v) for k, v in d["narrations"].items()},
            list(d["marks"]),
            d.get("focus"),
        )


def pending(game: Game, state: GameState) -> Nudge | None:
    """The nudge shown for the move the learner is about to play, if any."""
    d = game.bot_params.get("nudge")
    if not d or d["move_number"] != len(state.moves) + 1 or "narrations" not in d:
        return None
    return Nudge.from_json(d)


def _store(session: Session, game: Game, nudge: Nudge | None, *, count: bool) -> None:
    params = dict(game.bot_params)
    if nudge is None:
        params.pop("nudge", None)
    else:
        params["nudge"] = nudge.to_json()
    game.bot_params = params
    if count:
        game.nudges_used += 1
    session.add(game)
    session.commit()


async def preview(
    session: Session,
    game: Game,
    user: User,
    state: GameState,
    point: Point,
    *,
    engine: KataGoProcess | None,
    live: LiveAnalysis,
) -> Nudge | None:
    """The nudge for this ghost move, or None (no budget, no engine, or a fine move)."""
    gtp = point_to_gtp(point, state.size)
    shown = pending(game, state)
    if shown is not None and shown.point == gtp:
        return shown  # the same ghost again: same nudge, no budget used
    if engine is None or nudges_left(game, user) == 0 or state.to_move.value != _learner(game):
        return None
    with live.previewing():
        return await _check(session, game, user, state, point, gtp, engine, live)


async def _check(
    session: Session,
    game: Game,
    user: User,
    state: GameState,
    point: Point,
    gtp: str,
    engine: KataGoProcess,
    live: LiveAnalysis,
) -> Nudge | None:
    limit = game_threshold(session, game)
    mover = state.to_move
    number = len(state.moves) + 1
    rank = learner_rank(user.belt, user.rank_estimate)
    # the position after the ghost move (and the human policy) run while the position before
    # finishes its background analysis: the preview waits for the slower one, not the sum
    aq = live_query(f"{game.id}-nudge{number}-{gtp}", play(state, point), max_visits=AFTER_VISITS)
    queries = [asyncio.ensure_future(engine.analyze(aq, timeout=5))]
    if uses_p_find(user.belt):
        hq = human_policy_query(
            f"{game.id}-nudgehp{number}", state, [len(state.moves)], target_profile(rank)
        )
        hq.priority = LIVE_PRIORITY
        queries.append(asyncio.ensure_future(engine.analyze(hq, timeout=5)))
    try:
        before = await live.get(game.id, state)
        quick = quick_loss(before, gtp, mover)
        if quick is not None and quick < limit * FAST_SKIP:
            return None  # KataGo already rates this move fine
        results = await asyncio.gather(*queries)
    except (TimeoutError, EngineError):
        log.info("nudge skipped: engine busy game=%s", game.id)
        return None
    finally:
        for q in queries:
            q.cancel()  # unfinished queries are terminated in KataGo
    after = results[0][0]
    ctx = MoveContext(state_before=state, move=point, before=before, after=after)
    found = decide(ctx, number, user.belt, limit, None)
    if found is None:
        return None
    review, hit = found
    if len(results) > 1:
        hp = results[1][0].humanPolicy
        pf = p_find(hp, hit.correct_moves, state.size) if hp else None
        if decide(ctx, number, user.belt, limit, pf) is None:
            return None
    learner = learner_info(user.belt, rank)
    pkgs = {loc: nudge_package(review, hit, locale=loc, learner=learner) for loc in LOCALES}
    pkg = pkgs["en"]
    nudge = Nudge(
        move_number=number,
        point=gtp,
        concept_id=hit.concept_id,
        narrations={loc: render(p) for loc, p in pkgs.items()},
        marks=sorted({s for g in pkg.groups[:1] for s in g.stones}),
        focus=focus_area(hit.correct_moves, state.size),
    )
    _store(session, game, nudge, count=True)
    log.debug("nudge game=%s move=%d %s", game.id, number, hit.concept_id)
    return nudge


def _learner(game: Game) -> str:
    return "B" if game.learner_color == "black" else "W"


def after_move(session: Session, game: Game, state_before: GameState, point: str | None) -> None:
    """Mark the learner's move as nudged / played anyway, and clear the pending nudge."""
    shown = pending(game, state_before)
    if shown is None:
        return
    number = len(state_before.moves) + 1
    move = session.exec(select(Move).where(Move.game_id == game.id, Move.number == number)).first()
    if move is not None:
        move.nudge_shown = True
        move.played_anyway = point == shown.point
        session.add(move)
    _store(session, game, None, count=False)
