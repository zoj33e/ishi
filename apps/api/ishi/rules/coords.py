"""The only place that converts coordinates (backend side).

Internal points are `(x, y)` with `x = 0` the left column and `y = 0` the TOP row.
- GTP: columns `A`-`T` skipping `I`, rows counted from the bottom (`A1` = bottom-left). `pass`.
- SGF: two letters `xy`, both from the top-left (`aa` = top-left). Pass is `""` (or `tt` on ≤ 19).
- Index: row-major from the top-left, `y * size + x` (matches KataGo ownership/policy arrays).
"""

from typing import NamedTuple

GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST"
SGF_LETTERS = "abcdefghijklmnopqrstuvwxyz"
MIN_SIZE, MAX_SIZE = 2, 19
PASS = "pass"


class Point(NamedTuple):
    x: int
    y: int


def check_size(size: int) -> None:
    if not MIN_SIZE <= size <= MAX_SIZE:
        raise ValueError(f"board size {size} outside {MIN_SIZE}..{MAX_SIZE}")


def on_board(p: Point, size: int) -> bool:
    return 0 <= p.x < size and 0 <= p.y < size


def gtp_to_point(s: str, size: int) -> Point | None:
    """`"E5"` -> Point; `"pass"` -> None. Raises ValueError for anything off the board."""
    check_size(size)
    t = s.strip().upper()
    if t == "PASS":
        return None
    if len(t) < 2 or t[0] not in GTP_COLUMNS or not t[1:].isdigit():
        raise ValueError(f"bad GTP coordinate {s!r}")
    p = Point(GTP_COLUMNS.index(t[0]), size - int(t[1:]))
    if not on_board(p, size):
        raise ValueError(f"GTP coordinate {s!r} off a {size}x{size} board")
    return p


def point_to_gtp(p: Point | None, size: int) -> str:
    check_size(size)
    if p is None:
        return PASS
    if not on_board(p, size):
        raise ValueError(f"{p} off a {size}x{size} board")
    return f"{GTP_COLUMNS[p.x]}{size - p.y}"


def sgf_to_point(s: str, size: int) -> Point | None:
    """`"ee"` -> Point; `""` (and `"tt"` on boards ≤ 19) -> None (pass)."""
    check_size(size)
    if s == "" or (s == "tt" and size <= 19):
        return None
    if len(s) != 2 or s[0] not in SGF_LETTERS or s[1] not in SGF_LETTERS:
        raise ValueError(f"bad SGF coordinate {s!r}")
    p = Point(SGF_LETTERS.index(s[0]), SGF_LETTERS.index(s[1]))
    if not on_board(p, size):
        raise ValueError(f"SGF coordinate {s!r} off a {size}x{size} board")
    return p


def point_to_sgf(p: Point | None, size: int) -> str:
    check_size(size)
    if p is None:
        return ""
    if not on_board(p, size):
        raise ValueError(f"{p} off a {size}x{size} board")
    return SGF_LETTERS[p.x] + SGF_LETTERS[p.y]


def point_to_index(p: Point, size: int) -> int:
    return p.y * size + p.x


def index_to_point(i: int, size: int) -> Point:
    return Point(i % size, i // size)
