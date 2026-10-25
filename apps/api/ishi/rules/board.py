"""Immutable Go board: stones, chains (groups) and liberties. No move-legality policy here."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

from ishi.rules.coords import Point, check_size, on_board


class Color(Enum):
    BLACK = "B"
    WHITE = "W"

    @property
    def opponent(self) -> Color:
        return Color.WHITE if self is Color.BLACK else Color.BLACK

    @classmethod
    def parse(cls, s: str) -> Color:
        t = s.strip().upper()
        if t in ("B", "BLACK"):
            return cls.BLACK
        if t in ("W", "WHITE"):
            return cls.WHITE
        raise ValueError(f"bad color {s!r}")


@lru_cache(maxsize=32)
def _neighbor_table(size: int) -> tuple[tuple[Point, ...], ...]:
    table = []
    for i in range(size * size):
        x, y = i % size, i // size
        cand = (Point(x - 1, y), Point(x + 1, y), Point(x, y - 1), Point(x, y + 1))
        table.append(tuple(p for p in cand if on_board(p, size)))
    return tuple(table)


@dataclass(frozen=True, slots=True)
class Group:
    color: Color
    stones: frozenset[Point]
    liberties: frozenset[Point]

    @property
    def size(self) -> int:
        return len(self.stones)


@dataclass(frozen=True, slots=True)
class Board:
    size: int
    cells: tuple[Color | None, ...]

    @classmethod
    def empty(cls, size: int) -> Board:
        check_size(size)
        return cls(size, (None,) * (size * size))

    @classmethod
    def from_stones(
        cls, size: int, black: Iterable[Point] = (), white: Iterable[Point] = ()
    ) -> Board:
        """Place stones as-is (setup positions). Does not resolve captures."""
        board = cls.empty(size)
        cells = list(board.cells)
        for color, pts in ((Color.BLACK, black), (Color.WHITE, white)):
            for p in pts:
                if not on_board(p, size):
                    raise ValueError(f"{p} off a {size}x{size} board")
                cells[p.y * size + p.x] = color
        return cls(size, tuple(cells))

    @classmethod
    def from_rows(cls, rows: Iterable[str]) -> Board:
        """Parse an ASCII diagram, top row first: `X` black, `O` white, `.`/`+` empty."""
        lines = [r.replace(" ", "") for r in rows if r.strip()]
        size = len(lines)
        black, white = [], []
        for y, line in enumerate(lines):
            if len(line) != size:
                raise ValueError(f"row {y} has {len(line)} points, expected {size}")
            for x, ch in enumerate(line):
                if ch == "X":
                    black.append(Point(x, y))
                elif ch == "O":
                    white.append(Point(x, y))
                elif ch not in ".+":
                    raise ValueError(f"bad board char {ch!r}")
        return cls.from_stones(size, black, white)

    def to_rows(self) -> list[str]:
        sym = {None: ".", Color.BLACK: "X", Color.WHITE: "O"}
        return [
            "".join(sym[self.cells[y * self.size + x]] for x in range(self.size))
            for y in range(self.size)
        ]

    def __getitem__(self, p: Point) -> Color | None:
        return self.cells[p.y * self.size + p.x]

    def neighbors(self, p: Point) -> tuple[Point, ...]:
        return _neighbor_table(self.size)[p.y * self.size + p.x]

    def points(self) -> Iterator[Point]:
        for y in range(self.size):
            for x in range(self.size):
                yield Point(x, y)

    def stones(self, color: Color) -> list[Point]:
        return [p for p in self.points() if self[p] is color]

    def group_at(self, p: Point) -> Group | None:
        color = self[p]
        if color is None:
            return None
        stones = {p}
        libs: set[Point] = set()
        stack = [p]
        while stack:
            q = stack.pop()
            for n in self.neighbors(q):
                c = self[n]
                if c is None:
                    libs.add(n)
                elif c is color and n not in stones:
                    stones.add(n)
                    stack.append(n)
        return Group(color, frozenset(stones), frozenset(libs))

    def groups(self, color: Color | None = None) -> list[Group]:
        seen: set[Point] = set()
        out = []
        for p in self.points():
            c = self[p]
            if c is None or p in seen or (color is not None and c is not color):
                continue
            g = self.group_at(p)
            assert g is not None
            seen |= g.stones
            out.append(g)
        return out

    def with_changes(self, set_to: dict[Point, Color | None]) -> Board:
        cells = list(self.cells)
        for p, c in set_to.items():
            cells[p.y * self.size + p.x] = c
        return Board(self.size, tuple(cells))

    def place(self, p: Point, color: Color) -> tuple[Board, frozenset[Point]]:
        """Put a stone on an empty point and remove opponent chains left without liberties.

        Returns (new board, captured points). Does NOT check suicide or ko; see `ishi.rules.game`.
        """
        if self[p] is not None:
            raise ValueError(f"{p} is occupied")
        after = self.with_changes({p: color})
        captured: set[Point] = set()
        for n in after.neighbors(p):
            if after[n] is color.opponent and n not in captured:
                g = after.group_at(n)
                assert g is not None
                if not g.liberties:
                    captured |= g.stones
        if captured:
            after = after.with_changes(dict.fromkeys(captured))
        return after, frozenset(captured)
