"""C2 ignored_atari: a learner group was in atari, could be saved, and the learner left it to be
captured. Skipped when KataGo's best move also gives the group up (a correct sacrifice)."""

from __future__ import annotations

from ishi.rules.board import Board, Color, Group
from ishi.rules.coords import Point
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.facts import groups_in_atari
from ishi.why.ladder import ladder_start

MIN_POINTS_LOST = 2.0

CONCEPT = "ignored_atari"


def saves(board: Board, group: Group, move: Point | None, color: Color, ko: Point | None) -> bool:
    """Does `move` rescue the group in atari? Extending to 3+ liberties, or to 2 liberties that
    aren't a working ladder, or capturing an attacker chain next to it."""
    if move is None or board[move] is not None or move == ko:
        return False
    after, captured = board.place(move, color)
    chain = after.group_at(next(iter(group.stones)))
    if chain is None or not after.group_at(move):
        return False
    if captured and any(n in captured for s in group.stones for n in board.neighbors(s)):
        return True
    libs = len(chain.liberties)
    if move not in chain.stones:  # didn't touch the group and captured nothing next to it
        return False
    return libs >= 3 or (libs == 2 and ladder_start(after, move) is None)


def save_moves(ctx: MoveContext, group: Group) -> list[Point]:
    board = ctx.board_before
    ko = ctx.state_before.ko_point
    candidates = set(group.liberties)
    for s in group.stones:  # capture points of attacker chains in atari next to the group
        for n in board.neighbors(s):
            if board[n] is ctx.learner.opponent:
                chain = board.group_at(n)
                if chain and len(chain.liberties) == 1:
                    candidates |= chain.liberties
    return sorted(m for m in candidates if saves(board, group, m, ctx.learner, ko))


def detect(ctx: MoveContext) -> ConceptHit | None:
    if ctx.points_lost < MIN_POINTS_LOST:
        return None
    found = []
    for g in groups_in_atari(ctx.board_before, ctx.learner):
        savers = save_moves(ctx, g)
        if not savers:
            continue
        if ctx.move in savers:
            continue
        top = ctx.point(ctx.top_before.move)
        if top not in savers:  # KataGo gives the group up too: sacrifice, not a mistake
            continue
        stone = next(iter(g.stones))
        now = ctx.board_after.group_at(stone) if ctx.board_after[stone] is ctx.learner else None
        if now is None or len(now.liberties) != 1:
            continue
        (last,) = now.liberties
        if last == ctx.state_after.ko_point:  # opponent can't capture right away
            continue
        found.append((g, savers, top))
    if not found:
        return None
    g, savers, top = max(found, key=lambda f: len(f[0].stones))
    best = set(ctx.best_points)
    correct = [m for m in savers if m in best] or [top]
    (liberty,) = g.liberties
    return ConceptHit(
        CONCEPT,
        ctx.points_lost,
        {"save_move": ctx.gtp(correct[0]), "liberty_point": ctx.gtp(liberty)},
        [g.stones],
        {
            "group": ctx.gtps(g.stones),
            "liberty_point": ctx.gtp(liberty),
            "save_move": ctx.gtp(correct[0]),
            "size": len(g.stones),
        },
        [ctx.gtp(m) for m in correct],
    )
