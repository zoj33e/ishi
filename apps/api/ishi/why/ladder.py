"""Ladder reader (05-why-engine): does chasing this group with ataris capture it?

Pure board reading, no KataGo. The attacker keeps the defender at one liberty; the defender
extends on its last liberty (or captures an attacker chain in atari). Read stops when:
- the defender is captured or cannot extend (ladder **works**);
- the defender reaches 3+ liberties, or 2 liberties the attacker cannot take away with an atari,
  or captures an attacker chain (ladder **broken**). If the escape connected to another defender
  chain, one of its stones is reported as the `breaker`.
Ko is ignored; at most 80 plies.
"""

from __future__ import annotations

from dataclasses import dataclass

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point

MAX_PLIES = 80


@dataclass(frozen=True)
class LadderResult:
    works: bool
    path: tuple[Point, ...]  # moves played in the read, attacker first if it starts with an atari
    breaker: Point | None = None


def read_ladder(board: Board, target: Point) -> LadderResult:
    """Read the ladder on the chain at `target`.

    If the chain has 1 liberty, the defender moves first (it tries to run); with 2 liberties the
    attacker moves first (it tries to start the ladder). Other liberty counts: not a ladder.
    """
    group = board.group_at(target)
    if group is None:
        raise ValueError(f"no stone at {target}")
    libs = len(group.liberties)
    if libs == 1:
        return _defend(board, target, group.color, (), 0)
    if libs == 2:
        return _attack(board, target, group.color, (), 0)
    return LadderResult(False, ())


def ladder_start(board: Board, target: Point) -> LadderResult | None:
    """For a 2-liberty chain: the working ladder (path starts with the attacker's atari), if any."""
    group = board.group_at(target)
    if group is None or len(group.liberties) != 2:
        return None
    result = _attack(board, target, group.color, (), 0)
    return result if result.works else None


def _attack(
    board: Board, target: Point, defender: Color, path: tuple[Point, ...], plies: int
) -> LadderResult:
    group = board.group_at(target)
    assert group is not None
    if plies >= MAX_PLIES:
        return LadderResult(False, path)
    attacker = defender.opponent
    failed: list[LadderResult] = []
    for lib in sorted(group.liberties):
        after, _ = board.place(lib, attacker)
        mine = after.group_at(lib)
        assert mine is not None
        if not mine.liberties:  # suicide for the attacker
            continue
        chased = after.group_at(target)
        if chased is None:  # captured outright
            return LadderResult(True, (*path, lib))
        if len(chased.liberties) != 1:
            continue
        result = _defend(after, target, defender, (*path, lib), plies + 1)
        if result.works:
            return result
        failed.append(result)
    if not failed:
        return LadderResult(False, path)
    # Report the most telling failed chase: one that ran into a breaker, else the longest.
    return max(failed, key=lambda r: (r.breaker is not None, len(r.path)))


def _defend(
    board: Board, target: Point, defender: Color, path: tuple[Point, ...], plies: int
) -> LadderResult:
    group = board.group_at(target)
    assert group is not None
    if plies >= MAX_PLIES:
        return LadderResult(False, path)
    attacker = defender.opponent
    # Capturing an attacker chain in atari next to the defender breaks the ladder.
    for s in group.stones:
        for n in board.neighbors(s):
            if board[n] is attacker:
                chain = board.group_at(n)
                assert chain is not None
                if len(chain.liberties) == 1:
                    (cap,) = chain.liberties
                    return LadderResult(False, (*path, cap))
    (run,) = group.liberties
    after, _ = board.place(run, defender)
    extended = after.group_at(run)
    assert extended is not None
    new_path = (*path, run)
    libs = len(extended.liberties)
    if libs <= 1:
        return LadderResult(True, new_path)
    joined = [p for p in extended.stones - group.stones if p != run]
    breaker = min(joined) if joined else None
    if libs >= 3:
        return LadderResult(False, new_path, breaker)
    result = _attack(after, target, defender, new_path, plies + 1)
    if not result.works and result.breaker is None and breaker is not None:
        return LadderResult(False, result.path, breaker)
    return result
