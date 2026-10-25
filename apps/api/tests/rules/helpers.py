from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, gtp_to_point
from ishi.rules.game import GameState, new_game, play


def pt(gtp: str, size: int = 9) -> Point:
    p = gtp_to_point(gtp, size)
    assert p is not None
    return p


def position(rows: list[str], to_move: Color = Color.BLACK, komi: float = 7) -> GameState:
    """Game starting from an ASCII diagram (top row first)."""
    board = Board.from_rows(rows)
    return new_game(board.size, komi, initial_board=board, to_move=to_move)


def moves(state: GameState, *gtps: str) -> GameState:
    for g in gtps:
        state = play(state, gtp_to_point(g, state.size))
    return state
