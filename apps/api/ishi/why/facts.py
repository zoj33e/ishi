"""Board facts for the Why Engine (05-why-engine): pure functions of the rules-engine board.

No KataGo here. Detectors combine these facts with the analysis numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from ishi.rules.board import Board, Color, Group
from ishi.rules.coords import Point
from ishi.why.groups import false_eyes, true_eyes


def groups_in_atari(board: Board, color: Color) -> list[Group]:
    return [g for g in board.groups(color) if len(g.liberties) == 1]


def groups_with_two_liberties(board: Board, color: Color) -> list[Group]:
    return [g for g in board.groups(color) if len(g.liberties) == 2]


def capture_point(board: Board, group: Group, ko_point: Point | None = None) -> Point | None:
    """The point that captures `group` right now, if it is in atari and the capture is legal."""
    if len(group.liberties) != 1:
        return None
    (p,) = group.liberties
    return None if p == ko_point else p


def capturable_groups(
    board: Board, capturer: Color, ko_point: Point | None = None
) -> list[tuple[Group, Point]]:
    """Opponent groups `capturer` can take with one legal move, with that move."""
    out = []
    for g in groups_in_atari(board, capturer.opponent):
        p = capture_point(board, g, ko_point)
        if p is not None:
            out.append((g, p))
    return out


def cutting_points(board: Board, color: Color) -> dict[Point, list[Group]]:
    """Empty points where `color`'s chains could be cut apart.

    A point P is a cutting point when it touches two chains of `color` whose only shared liberty
    is P (two shared liberties = miai, effectively connected).
    """
    out: dict[Point, list[Group]] = {}
    chains = board.groups(color)
    by_lib: dict[Point, list[Group]] = {}
    for g in chains:
        for lib in g.liberties:
            by_lib.setdefault(lib, []).append(g)
    for p, gs in by_lib.items():
        if len(gs) < 2:
            continue
        cut = [pair for pair in combinations(gs, 2) if pair[0].liberties & pair[1].liberties == {p}]
        if cut:
            members: list[Group] = []
            for a, b in cut:
                for g in (a, b):
                    if g not in members:
                        members.append(g)
            out[p] = members
    return out


@dataclass(frozen=True)
class EyeFacts:
    true_eyes: frozenset[Point]
    false_eyes: frozenset[Point]


def eye_facts(board: Board, group: Group) -> EyeFacts:
    return EyeFacts(frozenset(true_eyes(board, group)), frozenset(false_eyes(board, group)))


@dataclass(frozen=True)
class GroupChange:
    stones: frozenset[Point]  # the group's stones before the move
    liberties_before: frozenset[Point]
    liberties_after: frozenset[Point]  # of the chain holding those stones after (empty if captured)
    captured: bool


@dataclass(frozen=True)
class MoveDiff:
    captured: frozenset[Point]
    new_atari: list[Group]  # groups (either color) in atari after the move that weren't before
    changes: list[GroupChange]  # every group that existed before the move


def move_diff(before: Board, after: Board, captured: frozenset[Point]) -> MoveDiff:
    atari_before = {g.stones for g in before.groups() if len(g.liberties) == 1}
    new_atari = [
        g for g in after.groups() if len(g.liberties) == 1 and g.stones not in atari_before
    ]
    changes = []
    for g in before.groups():
        p = next(iter(g.stones))
        now = after.group_at(p) if after[p] is g.color else None
        changes.append(
            GroupChange(
                g.stones,
                g.liberties,
                now.liberties if now else frozenset(),
                captured=now is None,
            )
        )
    return MoveDiff(captured, new_atari, changes)
