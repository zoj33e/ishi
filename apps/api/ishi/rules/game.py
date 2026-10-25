"""Game state and move legality. Authoritative rules (D-007), matching KataGo's
`{"ko":"SIMPLE","scoring":"AREA","suicide":false}`:

- Suicide is illegal: a move whose own chain has no liberties after captures are removed.
- Simple ko: a move that captures exactly one stone with a lone stone that is then left with
  exactly one liberty bans the opponent from immediately recapturing at that point. Any other
  move (including a pass) lifts the ban.
- Two consecutive passes end the game.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import Enum

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, on_board

DEFAULT_KOMI = 7.0


class Legality(Enum):
    OK = "ok"
    OCCUPIED = "occupied"
    SUICIDE = "suicide"
    KO = "ko"
    OFF_BOARD = "off_board"
    GAME_OVER = "game_over"


class IllegalMoveError(ValueError):
    def __init__(self, point: Point | None, reason: Legality) -> None:
        super().__init__(f"illegal move {point}: {reason.value}")
        self.point = point
        self.reason = reason


@dataclass(frozen=True, slots=True)
class Move:
    color: Color
    point: Point | None  # None = pass
    captured: frozenset[Point] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class GameState:
    board: Board
    to_move: Color
    komi: float = DEFAULT_KOMI
    ko_point: Point | None = None
    captures_black: int = 0  # stones captured BY black
    captures_white: int = 0  # stones captured BY white
    moves: tuple[Move, ...] = ()
    consecutive_passes: int = 0
    # Setup position before `moves` (handicap / puzzles); kept for SGF and KataGo queries.
    initial_board: Board | None = None
    initial_player: Color = Color.BLACK

    @property
    def size(self) -> int:
        return self.board.size

    @property
    def is_over(self) -> bool:
        return self.consecutive_passes >= 2

    @property
    def move_number(self) -> int:
        return len(self.moves)

    @property
    def last_move(self) -> Move | None:
        return self.moves[-1] if self.moves else None

    def captures(self, color: Color) -> int:
        return self.captures_black if color is Color.BLACK else self.captures_white


def new_game(
    size: int = 9,
    komi: float = DEFAULT_KOMI,
    *,
    initial_board: Board | None = None,
    to_move: Color = Color.BLACK,
) -> GameState:
    board = initial_board if initial_board is not None else Board.empty(size)
    if board.size != size:
        raise ValueError("initial board size mismatch")
    return GameState(
        board=board,
        to_move=to_move,
        komi=komi,
        initial_board=initial_board,
        initial_player=to_move,
    )


def check_move(state: GameState, point: Point | None) -> Legality:
    if state.is_over:
        return Legality.GAME_OVER
    if point is None:
        return Legality.OK
    if not on_board(point, state.size):
        return Legality.OFF_BOARD
    if state.board[point] is not None:
        return Legality.OCCUPIED
    if point == state.ko_point:
        return Legality.KO
    after, _ = state.board.place(point, state.to_move)
    group = after.group_at(point)
    assert group is not None
    if not group.liberties:
        return Legality.SUICIDE
    return Legality.OK


def is_legal(state: GameState, point: Point | None) -> bool:
    return check_move(state, point) is Legality.OK


def legal_moves(state: GameState) -> set[Point]:
    """All legal board points for the player to move (pass is always legal unless game over)."""
    if state.is_over:
        return set()
    return {p for p in state.board.points() if check_move(state, p) is Legality.OK}


def play(state: GameState, point: Point | None) -> GameState:
    reason = check_move(state, point)
    if reason is not Legality.OK:
        raise IllegalMoveError(point, reason)
    color = state.to_move
    if point is None:
        return replace(
            state,
            to_move=color.opponent,
            ko_point=None,
            moves=(*state.moves, Move(color, None)),
            consecutive_passes=state.consecutive_passes + 1,
        )
    after, captured = state.board.place(point, color)
    ko_point = None
    if len(captured) == 1:
        group = after.group_at(point)
        assert group is not None
        if group.size == 1 and len(group.liberties) == 1:
            ko_point = next(iter(captured))
    n = len(captured)
    return replace(
        state,
        board=after,
        to_move=color.opponent,
        ko_point=ko_point,
        captures_black=state.captures_black + (n if color is Color.BLACK else 0),
        captures_white=state.captures_white + (n if color is Color.WHITE else 0),
        moves=(*state.moves, Move(color, point, captured)),
        consecutive_passes=0,
    )


def replay(state: GameState, points: Iterable[Point | None]) -> GameState:
    for p in points:
        state = play(state, p)
    return state
