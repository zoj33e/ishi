"""What every detector sees about one learner move, and what a detector reports (05-why-engine)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from ishi.engine.models import AnalysisResponse, MoveInfo
from ishi.engine.queries import best_move_set, for_player, points_lost, top_move
from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp, point_to_index
from ishi.rules.game import GameState, play


@dataclass(frozen=True)
class MoveContext:
    """The learner's move with KataGo's view of the position before and after it.

    `before` analyzes the position the learner moved in (learner to play); `after` the position
    right after the move (opponent to play). Raw KataGo values are Black-perspective; use the
    helpers here to read them from the learner's side.
    """

    state_before: GameState
    move: Point | None  # None = pass
    before: AnalysisResponse
    after: AnalysisResponse

    @cached_property
    def state_after(self) -> GameState:
        return play(self.state_before, self.move)

    @property
    def learner(self) -> Color:
        return self.state_before.to_move

    @property
    def size(self) -> int:
        return self.state_before.size

    @property
    def board_before(self) -> Board:
        return self.state_before.board

    @property
    def board_after(self) -> Board:
        return self.state_after.board

    @property
    def captured(self) -> frozenset[Point]:
        last = self.state_after.last_move
        return last.captured if last else frozenset()

    @cached_property
    def points_lost(self) -> float:
        return points_lost(self.before, self.after, self.learner)

    @cached_property
    def best_moves(self) -> list[str]:
        """GTP moves in KataGo's best set for the learner (pass included as "pass")."""
        return best_move_set(self.before, self.learner)

    @cached_property
    def best_points(self) -> list[Point]:
        out = []
        for m in self.best_moves:
            p = gtp_to_point(m, self.size)
            if p is not None:
                out.append(p)
        return out

    @property
    def top_before(self) -> MoveInfo:
        return top_move(self.before)

    @property
    def top_after(self) -> MoveInfo:
        """The opponent's best reply to the learner's move."""
        return top_move(self.after)

    def gtp(self, p: Point | None) -> str:
        return point_to_gtp(p, self.size)

    def point(self, gtp: str) -> Point | None:
        return gtp_to_point(gtp, self.size)

    def ownership(self, stones: frozenset[Point], ownership_black: Sequence[float] | None) -> float:
        """Average ownership of `stones` from the learner's side (+1 = learner owns them)."""
        if not ownership_black or not stones:
            return 0.0
        total = sum(ownership_black[point_to_index(p, self.size)] for p in stones)
        return for_player(total / len(stones), self.learner)

    def gtps(self, points: frozenset[Point] | set[Point]) -> list[str]:
        return sorted(self.gtp(p) for p in points)


@dataclass(frozen=True)
class ConceptHit:
    concept_id: str
    severity_points: float  # = pointsLost
    key_points: dict[str, str]  # role -> GTP, e.g. {"capture_point": "E5"}
    groups: list[frozenset[Point]]  # stones involved, learner's first when it matters
    evidence: dict[str, Any]
    correct_moves: list[str]  # GTP
    variant: str | None = None  # ladder: broken_ladder_chase / ran_into_ladder
    secondary: list[str] = field(default_factory=list)

    def to_json(self, size: int) -> dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "variant": self.variant,
            "severity_points": round(self.severity_points, 2),
            "key_points": self.key_points,
            "groups": [sorted(point_to_gtp(p, size) for p in g) for g in self.groups],
            "evidence": self.evidence,
            "correct_moves": self.correct_moves,
            "secondary": self.secondary,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any], size: int) -> ConceptHit:
        groups = [
            frozenset(p for p in (gtp_to_point(s, size) for s in g) if p is not None)
            for g in data["groups"]
        ]
        return cls(
            data["concept_id"],
            data["severity_points"],
            data["key_points"],
            groups,
            data["evidence"],
            data["correct_moves"],
            data.get("variant"),
            data.get("secondary", []),
        )
