"""Simple shape facts used by the rules school now and the Why Engine later (M4).

Eyes here are single-point eyes: a liberty of the group whose orthogonal neighbors are all stones
of the group's color (they may belong to other chains, as in a false eye).
False eye (beginner rule): on the edge or in the corner any opponent stone on a diagonal makes it
false; in the middle two or more opponent diagonals do.
"""

from ishi.rules.board import Board, Group
from ishi.rules.coords import Point, on_board


def eye_points(board: Board, group: Group) -> set[Point]:
    return {
        lib for lib in group.liberties if all(board[n] is group.color for n in board.neighbors(lib))
    }


def is_false_eye(board: Board, point: Point, group: Group) -> bool:
    diagonals = [
        Point(point.x + dx, point.y + dy)
        for dx in (-1, 1)
        for dy in (-1, 1)
        if on_board(Point(point.x + dx, point.y + dy), board.size)
    ]
    enemy = sum(1 for d in diagonals if board[d] is group.color.opponent)
    return enemy >= (1 if len(diagonals) < 4 else 2)


def true_eyes(board: Board, group: Group) -> set[Point]:
    return {p for p in eye_points(board, group) if not is_false_eye(board, p, group)}


def false_eyes(board: Board, group: Group) -> set[Point]:
    return {p for p in eye_points(board, group) if is_false_eye(board, p, group)}
