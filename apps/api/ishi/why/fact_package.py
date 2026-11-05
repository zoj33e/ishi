"""FactPackage: everything the teacher may say about one lesson (05-why-engine, 06-teacher-llm).

The teacher only rewrites these facts; `allowed_coordinates` is every coordinate in the package and
the validator rejects narration that mentions any other.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ishi.bots.humansl_bot import rank_label
from ishi.rules.board import Color
from ishi.rules.coords import gtp_to_point
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.review import MoveReview
from ishi.why.selector import Praise

FOLLOW_UP_PLIES = 4


class LearnerInfo(BaseModel):
    belt: str
    rank_estimate: str | None = None  # label, e.g. "24k"


class GroupFact(BaseModel):
    id: str
    owner: Literal["learner", "opponent"]
    stones: list[str]
    liberties_before: list[str]
    liberties_after: list[str]


class FactPackage(BaseModel):
    lesson_type: Literal["mistake", "praise", "nudge", "clean"]
    locale: Literal["th", "en"]
    learner: LearnerInfo
    board_size: int
    move_number: int | None = None
    learner_color: Literal["black", "white"]
    concept_id: str | None = None
    variant: str | None = None
    concept_is_new: bool = False
    praise_kind: str | None = None
    threat_move: str | None = None
    played_move: str | None = None
    correct_moves: list[str] = Field(default_factory=list)
    points_lost: float | None = None
    groups: list[GroupFact] = Field(default_factory=list)
    key_points: dict[str, str] = Field(default_factory=dict)
    follow_up_line: list[str] = Field(default_factory=list)
    secondary_concepts: list[str] = Field(default_factory=list)
    allowed_coordinates: list[str] = Field(default_factory=list)

    def finalize(self) -> FactPackage:
        """Fill `allowed_coordinates` with every coordinate mentioned anywhere in the package."""
        coords: set[str] = set()

        def add(v: Any) -> None:
            if isinstance(v, str):
                for token in v.split():
                    if _is_coord(token, self.board_size):
                        coords.add(token.upper())
            elif isinstance(v, dict):
                for x in v.values():
                    add(x)
            elif isinstance(v, list | tuple):
                for x in v:
                    add(x)

        add(self.model_dump(exclude={"allowed_coordinates", "locale", "concept_id", "variant"}))
        self.allowed_coordinates = sorted(coords)
        return self


def _is_coord(token: str, size: int) -> bool:
    if token.lower() == "pass":
        return False
    try:
        return gtp_to_point(token, size) is not None
    except ValueError:
        return False


def _color(c: Color) -> Literal["black", "white"]:
    return "black" if c is Color.BLACK else "white"


def _group_facts(ctx: MoveContext, hit: ConceptHit) -> list[GroupFact]:
    out = []
    for i, stones in enumerate(hit.groups, start=1):
        if not stones:
            continue
        p = next(iter(stones))
        color = ctx.board_before[p] or ctx.board_after[p]
        before = ctx.board_before.group_at(p) if ctx.board_before[p] is not None else None
        after = ctx.board_after.group_at(p) if ctx.board_after[p] is color else None
        out.append(
            GroupFact(
                id=f"g{i}",
                owner="learner" if color is ctx.learner else "opponent",
                stones=ctx.gtps(stones),
                liberties_before=ctx.gtps(before.liberties) if before else [],
                liberties_after=ctx.gtps(after.liberties) if after else [],
            )
        )
    return out


def follow_up(ctx: MoveContext) -> list[str]:
    """The opponent's best answer to the learner's move and how it continues."""
    pv = ctx.top_after.pv or [ctx.top_after.move]
    color = ctx.learner.opponent
    out = []
    for m in pv[:FOLLOW_UP_PLIES]:
        out.append(f"{color.value} {m.upper() if m.lower() != 'pass' else 'pass'}")
        color = color.opponent
    return out


def mistake_package(
    review: MoveReview,
    hit: ConceptHit,
    *,
    locale: Literal["th", "en"],
    learner: LearnerInfo,
    concept_is_new: bool,
) -> FactPackage:
    ctx = review.ctx
    return FactPackage(
        lesson_type="mistake",
        locale=locale,
        learner=learner,
        board_size=ctx.size,
        move_number=review.number,
        learner_color=_color(ctx.learner),
        concept_id=hit.concept_id,
        variant=hit.variant,
        concept_is_new=concept_is_new,
        played_move=review.move,
        correct_moves=hit.correct_moves,
        points_lost=round(review.points_lost, 1),
        groups=_group_facts(ctx, hit),
        key_points=hit.key_points,
        follow_up_line=follow_up(ctx),
        secondary_concepts=hit.secondary,
    ).finalize()


def praise_package(
    praise: Praise, *, locale: Literal["th", "en"], learner: LearnerInfo
) -> FactPackage:
    r = praise.review
    ctx = r.ctx
    stones = praise.group.stones
    after = ctx.board_after.group_at(next(iter(stones)))
    return FactPackage(
        lesson_type="praise",
        locale=locale,
        learner=learner,
        board_size=ctx.size,
        move_number=r.number,
        learner_color=_color(ctx.learner),
        praise_kind=praise.kind,
        threat_move=praise.threat_move,
        played_move=r.move,
        correct_moves=[r.move],
        groups=[
            GroupFact(
                id="g1",
                owner="learner",
                stones=ctx.gtps(stones),
                liberties_before=ctx.gtps(praise.group.liberties),
                liberties_after=ctx.gtps(after.liberties) if after else [],
            )
        ],
        key_points={"threat_move": praise.threat_move, "answer": r.move},
    ).finalize()


def clean_package(
    *, locale: Literal["th", "en"], learner: LearnerInfo, size: int, color: Color
) -> FactPackage:
    return FactPackage(
        lesson_type="clean",
        locale=locale,
        learner=learner,
        board_size=size,
        learner_color=_color(color),
    ).finalize()


def learner_info(belt: str, rank_estimate: float | None) -> LearnerInfo:
    return LearnerInfo(
        belt=belt, rank_estimate=rank_label(rank_estimate) if rank_estimate is not None else None
    )
