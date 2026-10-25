"""Capture Go rules and the capture bot (M2). Pure functions, no I/O.

Capture Go: the first player to capture `target` stones wins. A player may pass; two passes in a
row end the game and the player with more captures wins (equal = draw).

Bot levels (D-024): 1 = depth 1 + 30% random moves, 2 = depth 2 + 15%, 3 = depth 4, no random.
Order of thought: capture now if possible (largest), else save an own chain in atari if that
gives it 2+ liberties, else alpha-beta search on a liberty-based evaluation.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from ishi.rules.board import Color, Group
from ishi.rules.coords import Point
from ishi.rules.game import GameState, Legality, check_move, legal_moves, play

WIN = 1_000_000


@dataclass(frozen=True)
class Level:
    depth: int
    random_rate: float
    width: int  # moves searched per node after ordering


LEVELS = {
    1: Level(depth=1, random_rate=0.30, width=40),
    2: Level(depth=2, random_rate=0.15, width=12),
    3: Level(depth=4, random_rate=0.0, width=7),
}


# -- rules -------------------------------------------------------------------------------


def capture_winner(state: GameState, target: int) -> Color | None:
    """Winner once someone reached the target, or after two passes; None = still going / draw."""
    for c in (Color.BLACK, Color.WHITE):
        if state.captures(c) >= target:
            return c
    if state.consecutive_passes >= 2:
        b, w = state.captures_black, state.captures_white
        if b != w:
            return Color.BLACK if b > w else Color.WHITE
    return None


def capture_over(state: GameState, target: int) -> bool:
    return capture_winner(state, target) is not None or state.consecutive_passes >= 2


def capture_result(state: GameState, target: int) -> str:
    """ "B+C" / "W+C" / "Draw" for a finished capture game."""
    w = capture_winner(state, target)
    if w is None:
        return "Draw"
    return ("B" if w is Color.BLACK else "W") + "+C"


# -- bot ---------------------------------------------------------------------------------


class CaptureBot:
    def __init__(
        self,
        level: int,
        target: int,
        rng: random.Random | None = None,
        time_limit: float = 1.5,
    ) -> None:
        if level not in LEVELS:
            raise ValueError(f"unknown capture bot level {level}")
        self.level = LEVELS[level]
        self.target = target
        self.rng = rng or random.Random()
        self.time_limit = time_limit

    def choose(self, state: GameState) -> Point | None:
        """The bot's move for the player to move; None = pass (only when nothing is legal)."""
        legal = sorted(legal_moves(state))
        if not legal:
            return None
        cap = _best_capture(state, legal)
        if cap is not None:
            return cap
        if self.rng.random() < self.level.random_rate:
            return self.rng.choice(legal)
        esc = _escape(state)
        if esc is not None:
            return esc
        return self._search(state, legal)

    # Iterative deepening negamax with alpha-beta, cut off by time.
    def _search(self, state: GameState, legal: list[Point]) -> Point:
        deadline = time.monotonic() + self.time_limit
        root = _ordered(state, legal, self.target)
        width = max(self.level.width, 8)
        root = root[:width] if len(root) > width else root
        best = root[0]
        for depth in range(1, self.level.depth + 1):
            try:
                best = self._root(state, root, depth, deadline)
            except _Timeout:
                break
        return best

    def _root(self, state: GameState, moves: list[Point], depth: int, deadline: float) -> Point:
        alpha, beta = -WIN * 2, WIN * 2
        best_val = -WIN * 2
        tied: list[Point] = []
        for m in moves:
            v = -self._negamax(play(state, m), depth - 1, -beta, -alpha, deadline)
            if v > best_val:
                best_val, tied = v, [m]
            elif v == best_val:
                tied.append(m)
            alpha = max(alpha, v)
        return self.rng.choice(tied)

    def _negamax(
        self, state: GameState, depth: int, alpha: float, beta: float, deadline: float
    ) -> float:
        if time.monotonic() > deadline:
            raise _Timeout
        w = capture_winner(state, self.target)
        if w is not None:
            # Prefer quick wins and slow losses.
            return (WIN + depth) if w is state.to_move else -(WIN + depth)
        if depth == 0:
            return evaluate(state, self.target)
        moves = _candidates(state)
        if not moves:
            return evaluate(state, self.target)
        if depth > 1:
            moves = _ordered(state, moves, self.target)[: self.level.width]
        best = -WIN * 2
        for m in moves:
            v = -self._negamax(play(state, m), depth - 1, -beta, -alpha, deadline)
            best = max(best, v)
            alpha = max(alpha, v)
            if alpha >= beta:
                break
        return best


class _Timeout(Exception):
    pass


def evaluate(state: GameState, target: int) -> float:
    """Static score for the player to move (higher = better)."""
    me, opp = state.to_move, state.to_move.opponent
    score = 100.0 * (state.captures(me) - state.captures(opp))
    my_groups = state.board.groups(me)
    opp_groups = state.board.groups(opp)
    # It is my move: an opponent chain in atari can be taken right now.
    takeable = [g for g in opp_groups if len(g.liberties) == 1 and _can_play(state, g)]
    if takeable:
        biggest = max(g.size for g in takeable)
        if state.captures(me) + biggest >= target:
            return WIN / 2
        score += 80.0 * biggest
    # My chains in atari: I can save one at most, so count all but the biggest.
    mine_atari = sorted((g.size for g in my_groups if len(g.liberties) == 1), reverse=True)
    if len(mine_atari) >= 2:
        if state.captures(opp) + mine_atari[1] >= target:
            score -= WIN / 4
        score -= 60.0 * sum(mine_atari[1:])
    min_mine = min((len(g.liberties) for g in my_groups), default=4)
    min_opp = min((len(g.liberties) for g in opp_groups), default=4)
    score += 10.0 * (min(min_mine, 4) - min(min_opp, 4))
    mobility = sum(len(g.liberties) for g in my_groups) - sum(len(g.liberties) for g in opp_groups)
    score += 0.5 * mobility
    return score


def _can_play(state: GameState, g: Group) -> bool:
    return check_move(state, next(iter(g.liberties))) is Legality.OK


def _best_capture(state: GameState, legal: list[Point]) -> Point | None:
    best, best_n = None, 0
    for g in state.board.groups(state.to_move.opponent):
        if len(g.liberties) == 1:
            lib = next(iter(g.liberties))
            if lib in legal and g.size > best_n:
                best, best_n = lib, g.size
    return best


def _escape(state: GameState) -> Point | None:
    for g in sorted(state.board.groups(state.to_move), key=lambda g: -g.size):
        if len(g.liberties) != 1:
            continue
        lib = next(iter(g.liberties))
        if check_move(state, lib) is not Legality.OK:
            continue
        after = play(state, lib).board.group_at(lib)
        if after is not None and len(after.liberties) >= 2:
            return lib
    return None


def _candidates(state: GameState) -> list[Point]:
    """Moves worth searching: liberties of chains with few liberties, else any legal move."""
    pts: set[Point] = set()
    for g in state.board.groups():
        if len(g.liberties) <= 3:
            pts |= g.liberties
    legal = [p for p in sorted(pts) if check_move(state, p) is Legality.OK]
    return legal or sorted(legal_moves(state))


def _ordered(state: GameState, moves: list[Point], target: int) -> list[Point]:
    scored = [(-evaluate(play(state, m), target), m) for m in moves]
    scored.sort(key=lambda t: (-t[0], t[1].y, t[1].x))
    return [m for _, m in scored]
