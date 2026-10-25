"""Area scoring (stones + surrounded empty points), komi to White.

Dead stones are passed in explicitly (in M3 they come from KataGo ownership); they are removed
before counting, so their points count for whoever surrounds them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point


@dataclass(frozen=True, slots=True)
class Score:
    black_area: int
    white_area: int
    komi: float
    # Owner of each point after dead-stone removal (None = neutral / dame).
    territory: dict[Point, Color | None]

    @property
    def margin(self) -> float:
        """Black minus White, komi included. Positive = Black wins."""
        return self.black_area - (self.white_area + self.komi)

    @property
    def winner(self) -> Color | None:
        if self.margin > 0:
            return Color.BLACK
        if self.margin < 0:
            return Color.WHITE
        return None

    @property
    def result(self) -> str:
        """SGF-style result: `B+3.0`, `W+0.5`, or `0` for a draw (jigo)."""
        w = self.winner
        return "0" if w is None else f"{w.value}+{abs(self.margin):.1f}"


def area_score(board: Board, komi: float, dead: Iterable[Point] = ()) -> Score:
    dead_set = set(dead)
    for p in dead_set:
        if board[p] is None:
            raise ValueError(f"dead stone list contains empty point {p}")
    b = board.with_changes(dict.fromkeys(dead_set)) if dead_set else board

    owner: dict[Point, Color | None] = {}
    for p in b.points():
        c = b[p]
        if c is not None:
            owner[p] = c
            continue
        if p in owner:
            continue
        region, borders = _empty_region(b, p)
        region_owner = next(iter(borders)) if len(borders) == 1 else None
        for q in region:
            owner[q] = region_owner

    black = sum(1 for c in owner.values() if c is Color.BLACK)
    white = sum(1 for c in owner.values() if c is Color.WHITE)
    return Score(black, white, komi, owner)


def _empty_region(board: Board, start: Point) -> tuple[set[Point], set[Color]]:
    region = {start}
    borders: set[Color] = set()
    stack = [start]
    while stack:
        q = stack.pop()
        for n in board.neighbors(q):
            c = board[n]
            if c is None:
                if n not in region:
                    region.add(n)
                    stack.append(n)
            else:
                borders.add(c)
    return region, borders
