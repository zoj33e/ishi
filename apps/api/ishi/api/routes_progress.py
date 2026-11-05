"""Progress screen (M8): rank over time, the belt path, and the concepts that cost the most."""

from collections import Counter
from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import col, select

from ishi.bots.humansl_bot import rank_label
from ishi.db.models import Mistake, RankHistory
from ishi.db.session import SessionDep, get_or_create_user
from ishi.play import service
from ishi.play.progression import BELT_EXAM_MIN_GAMES, BELT_EXAM_RANK_MARGIN
from ishi.progress import service as progress
from ishi.why.detectors import UNEXPLAINED
from ishi.why.selector import BELT_RANK, BELTS

router = APIRouter(tags=["progress"])

CONCEPT_GAMES = 10  # concept stats over the last games
MVP_BELTS = BELTS[:-1]  # Black is post-MVP


class RankPoint(BaseModel):
    date: date
    rank_estimate: float
    likelihood_rank: float | None
    results_rank: float | None
    games_count: int


class ConceptStat(BaseModel):
    concept_id: str
    count: int  # mistakes of this concept in the last 10 games
    points_lost: float


class BeltStep(BaseModel):
    belt: str
    rank: float | None  # approx. rank (02-curriculum); None for White/Yellow
    status: Literal["done", "current", "next", "later"]


class ExamStatus(BaseModel):
    belt_target: str | None
    available: bool
    in_progress: str | None
    rank_needed: float | None  # the estimate must be at most this (Orange+)
    games_since_belt: int
    games_needed: int
    games_left: int  # games still to play (minimum since the belt, or the wait after a fail)


class ProgressOut(BaseModel):
    belt: str
    rank_estimate: float | None
    rank_label: str | None
    bot_rank: float
    bot_label: str
    games_played: int
    rank_history: list[RankPoint]
    concept_stats: list[ConceptStat]
    belts: list[BeltStep]
    exam: ExamStatus


@router.get("/progress", response_model=ProgressOut)
def get_progress(session: SessionDep) -> ProgressOut:
    user = get_or_create_user(session)
    history = session.exec(
        select(RankHistory).where(RankHistory.user_id == user.id).order_by(col(RankHistory.date))
    ).all()
    games = progress.finished_full_games(session, user.id)
    recent = {g.id for g in games[:CONCEPT_GAMES]}
    counts: Counter[str] = Counter()
    lost: Counter[str] = Counter()
    if recent:
        rows = session.exec(
            select(Mistake).where(
                col(Mistake.game_id).in_(recent), Mistake.concept_id != UNEXPLAINED
            )
        ).all()
        for m in rows:
            counts[m.concept_id] += 1
            lost[m.concept_id] += m.points_lost
    here = MVP_BELTS.index(user.belt) if user.belt in MVP_BELTS else len(MVP_BELTS)
    belts = [
        BeltStep(
            belt=b,
            rank=BELT_RANK.get(b),
            status="done"
            if i < here
            else "current"
            if i == here
            else "next"
            if i == here + 1
            else "later",
        )
        for i, b in enumerate(MVP_BELTS)
    ]
    target = service.next_belt(user)
    active = service.active_exam(session, user)
    belt_rank = BELT_RANK.get(target) if target else None
    bot = progress.default_bot_rank(user)
    return ProgressOut(
        belt=user.belt,
        rank_estimate=user.rank_estimate,
        rank_label=rank_label(user.rank_estimate) if user.rank_estimate is not None else None,
        bot_rank=bot,
        bot_label=rank_label(bot),
        games_played=len(games),
        rank_history=[
            RankPoint(
                date=h.date,
                rank_estimate=h.rank_estimate,
                likelihood_rank=h.likelihood_rank,
                results_rank=h.results_rank,
                games_count=h.games_count,
            )
            for h in history
        ],
        concept_stats=[
            ConceptStat(concept_id=c, count=n, points_lost=round(lost[c], 1))
            for c, n in counts.most_common()
        ],
        belts=belts,
        exam=ExamStatus(
            belt_target=target,
            available=service.can_take_exam(session, user),
            in_progress=active.id if active else None,
            rank_needed=belt_rank + BELT_EXAM_RANK_MARGIN if belt_rank is not None else None,
            games_since_belt=service.games_since_belt(session, user),
            games_needed=BELT_EXAM_MIN_GAMES,
            games_left=service.exam_games_left(session, user),
        ),
    )
