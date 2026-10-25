import pytest

from ishi.rules.coords import (
    GTP_COLUMNS,
    Point,
    gtp_to_point,
    index_to_point,
    point_to_gtp,
    point_to_index,
    point_to_sgf,
    sgf_to_point,
)


def test_gtp_columns_skip_i() -> None:
    assert "I" not in GTP_COLUMNS
    assert GTP_COLUMNS[:9] == "ABCDEFGHJ"


@pytest.mark.parametrize(
    ("gtp", "size", "point"),
    [
        ("A1", 9, Point(0, 8)),  # bottom-left
        ("A9", 9, Point(0, 0)),  # top-left
        ("J9", 9, Point(8, 0)),  # top-right: J, not I
        ("J1", 9, Point(8, 8)),
        ("E5", 9, Point(4, 4)),  # tengen
        ("H8", 9, Point(7, 1)),
        ("T19", 19, Point(18, 0)),
        ("K10", 19, Point(9, 9)),
        ("d4", 13, Point(3, 9)),  # lowercase accepted
    ],
)
def test_gtp_roundtrip(gtp: str, size: int, point: Point) -> None:
    assert gtp_to_point(gtp, size) == point
    assert point_to_gtp(point, size) == gtp.upper()


@pytest.mark.parametrize("bad", ["I5", "K1", "A10", "A0", "Z3", "", "E", "55", "E5.5"])
def test_gtp_rejects_off_board_and_garbage_on_9x9(bad: str) -> None:
    with pytest.raises(ValueError):
        gtp_to_point(bad, 9)


def test_pass_both_ways() -> None:
    assert gtp_to_point("pass", 9) is None
    assert gtp_to_point("PASS", 9) is None
    assert point_to_gtp(None, 9) == "pass"
    assert sgf_to_point("", 9) is None
    assert sgf_to_point("tt", 19) is None
    assert point_to_sgf(None, 9) == ""


def test_sgf_coords_from_top_left() -> None:
    assert sgf_to_point("aa", 9) == Point(0, 0)
    assert sgf_to_point("ia", 9) == Point(8, 0)  # SGF uses i
    assert point_to_sgf(Point(4, 4), 9) == "ee"
    assert point_to_gtp(sgf_to_point("ai", 9), 9) == "A1"
    with pytest.raises(ValueError):
        sgf_to_point("jj", 9)


def test_index_matches_katago_row_major_from_top_left() -> None:
    assert point_to_index(gtp_to_point("A9", 9), 9) == 0  # type: ignore[arg-type]
    assert point_to_index(gtp_to_point("J1", 9), 9) == 80  # type: ignore[arg-type]
    assert point_to_index(gtp_to_point("E5", 9), 9) == 40  # type: ignore[arg-type]
    assert all(
        index_to_point(point_to_index(Point(x, y), 13), 13) == Point(x, y)
        for x in range(13)
        for y in range(13)
    )


def test_bad_board_size() -> None:
    with pytest.raises(ValueError):
        gtp_to_point("A1", 20)
    with pytest.raises(ValueError):
        point_to_gtp(Point(9, 0), 9)
