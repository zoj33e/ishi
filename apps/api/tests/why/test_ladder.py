from ishi.rules.board import Board
from ishi.rules.coords import gtp_to_point, point_to_gtp
from ishi.why.ladder import ladder_start, read_ladder

E = "........."


def _read(rows: list[str], target: str) -> tuple[bool, list[str], str | None]:
    r = read_ladder(Board.from_rows(rows), gtp_to_point(target, 9))  # type: ignore[arg-type]
    return r.works, [point_to_gtp(p, 9) for p in r.path], r.breaker and point_to_gtp(r.breaker, 9)


LADDER = [E, E, E, E, E, "..O......", "..OX.....", "...O.....", E]


def test_working_ladder_runs_to_the_edge() -> None:
    works, path, breaker = _read(LADDER, "D3")
    assert works and breaker is None
    assert path[:4] == ["E3", "D4", "D5", "E4"]
    assert path[-1][0] == "J"  # captured at the right edge


def test_ladder_from_atari_defender_moves_first() -> None:
    rows = [E, E, E, E, E, "..O......", "..OX.....", "...OO....", E]
    works, path, _ = _read(rows, "D3")
    assert works and path[0] == "D4"  # the defender runs first


def test_ladder_breaker_stops_it() -> None:
    rows = [E, "......X..", *LADDER[2:]]
    works, path, breaker = _read(rows, "D3")
    assert not works and breaker == "G8"
    assert path[0] == "E3"


def test_white_stone_on_the_path_does_not_break_a_black_attack() -> None:
    rows = [E, E, "......O..", *LADDER[3:]]
    works, _, _ = _read(rows, "D3")
    assert works


def test_defender_captures_an_attacker_in_atari() -> None:
    # Black D3 in atari; the White D4 stone next to it is itself in atari at D5.
    rows = [E, E, E, E, E, "..XOX....", "..OX.....", "...O.....", E]
    works, path, _ = _read(rows, "D3")
    assert not works and path == ["D5"]


def test_edge_ladder() -> None:
    rows = [E, E, E, E, E, E, E, "..O.O....", "..OX....."]
    works, _, _ = _read(rows, "D1")
    assert works


def test_three_liberties_is_not_a_ladder() -> None:
    works, path, _ = _read([E, E, E, E, "....X....", E, E, E, E], "E5")
    assert not works and path == []


def test_ladder_start_only_for_two_liberty_chains() -> None:
    board = Board.from_rows(LADDER)
    start = ladder_start(board, gtp_to_point("D3", 9))  # type: ignore[arg-type]
    assert start is not None and point_to_gtp(start.path[0], 9) == "E3"
    lone = Board.from_rows([E, E, E, E, "....X....", E, E, E, E])
    assert ladder_start(lone, gtp_to_point("E5", 9)) is None  # type: ignore[arg-type]
