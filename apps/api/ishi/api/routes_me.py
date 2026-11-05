"""Profile and home (`/me`, `/today`)."""

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ishi.api.routes_school import next_lesson
from ishi.db.models import User, utcnow
from ishi.db.session import SessionDep, get_or_create_user
from ishi.play import lessons, service
from ishi.play.progression import STAGES

router = APIRouter(tags=["me"])


class MeOut(BaseModel):
    id: str
    display_name: str
    locale: Literal["th", "en"]
    belt: str
    rank_estimate: float | None
    streak: int
    settings: dict[str, Any]


class MePatch(BaseModel):
    locale: Literal["th", "en"] | None = None
    display_name: str | None = Field(default=None, max_length=40)
    settings: dict[str, Any] | None = None


class CaptureStageOut(BaseModel):
    stage: int
    stages_total: int
    board_size: int
    capture_target: int
    bot_level: int
    streak: int  # wins in a row at this stage (3 moves up)
    games_played: int


class TodayGame(BaseModel):
    mode: Literal["capture"]
    board_size: int
    bot_rank: float | None


class TodayOut(BaseModel):
    warmup_due: int
    game: TodayGame
    lesson_pending: str | None  # unfinished post-game lesson (M5)
    lesson_game: str | None  # its game, for the lesson screen URL
    school_next: str | None  # next rules-school lesson, None when all done
    capture: CaptureStageOut
    exam_available: bool
    exam_in_progress: str | None


def _me(user: User) -> MeOut:
    return MeOut(
        id=user.id,
        display_name=user.display_name,
        locale="en" if user.locale == "en" else "th",
        belt=user.belt,
        rank_estimate=user.rank_estimate,
        streak=0,
        settings=user.settings,
    )


@router.get("/me", response_model=MeOut)
def get_me(session: SessionDep) -> MeOut:
    return _me(get_or_create_user(session))


@router.patch("/me", response_model=MeOut)
def patch_me(session: SessionDep, body: MePatch) -> MeOut:
    user = get_or_create_user(session)
    if body.locale is not None:
        user.locale = body.locale
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.settings is not None:
        user.settings = {**user.settings, **body.settings}
    user.updated_at = utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return _me(user)


@router.get("/today", response_model=TodayOut)
def today(session: SessionDep) -> TodayOut:
    user = get_or_create_user(session)
    st = service.stage_status(session, user)
    exam = service.active_exam(session, user)
    pending = lessons.pending_lesson(session, user.id)
    return TodayOut(
        warmup_due=0,
        game=TodayGame(mode="capture", board_size=st.stage.board_size, bot_rank=None),
        lesson_pending=pending.id if pending else None,
        lesson_game=pending.game_id if pending else None,
        school_next=next_lesson(session, user),
        capture=CaptureStageOut(
            stage=st.stage.number,
            stages_total=len(STAGES),
            board_size=st.stage.board_size,
            capture_target=st.stage.target,
            bot_level=st.stage.level,
            streak=st.streak,
            games_played=st.games_played,
        ),
        exam_available=service.can_take_exam(session, user),
        exam_in_progress=exam.id if exam else None,
    )
