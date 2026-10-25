from ishi.engine.models import AnalysisResponse
from ishi.play.full_game import dame_fill, dead_stones, summarize
from ishi.rules.board import Board, Color
from ishi.rules.coords import point_to_gtp
from ishi.rules.game import new_game
from ishi.rules.scoring import area_score


def _ownership(rows: list[str]) -> list[float]:
    """'+' Black owns, '-' White owns, '.' neutral."""
    return [{"+": 1.0, "-": -1.0, ".": 0.0}[c] for row in rows for c in row]


def test_dead_stones_by_chain_ownership() -> None:
    board = Board.from_rows(
        [
            "..X..",
            ".X.O.",
            "XXOO.",
            "..O..",
            ".O...",
        ]
    )
    own = _ownership(
        [
            "++---",
            "++---",
            "++---",
            "++---",
            "++---",
        ]
    )
    dead = {point_to_gtp(p, 5) for p in dead_stones(board, own)}
    assert dead == {"C5", "B1"}  # black C5 in white's area, white B1 in black's
    score = area_score(board, 0, dead_stones(board, own))
    assert (score.black_area, score.white_area) == (3, 4)  # dead stones are not counted


def test_seki_like_neutral_stones_stay_alive() -> None:
    board = Board.from_rows(["X.O", "...", "..."])
    assert dead_stones(board, [0.0] * 9) == set()


def _resp(winrate: float, infos: list[tuple[str, float]]) -> AnalysisResponse:
    return AnalysisResponse.model_validate(
        {
            "id": "q",
            "turnNumber": 0,
            "moveInfos": [
                {
                    "move": m,
                    "visits": 10,
                    "winrate": 0.5,
                    "scoreLead": lead,
                    "prior": 0.1,
                    "order": i,
                }
                for i, (m, lead) in enumerate(infos)
            ],
            "rootInfo": {"winrate": winrate, "scoreLead": 0, "visits": 40, "currentPlayer": "W"},
        }
    )


def test_summary_converts_to_the_bots_view() -> None:
    s = summarize(_resp(0.9, [("D4", 5.0), ("pass", 4.8)]), Color.WHITE)
    assert round(s.winrate, 3) == 0.1
    assert s.best_move == "D4" and s.best_lead == -5.0 and s.pass_lead == -4.8


def test_dame_fill_picks_a_neutral_point_and_none_when_settled() -> None:
    board = Board.from_rows([".X.O.", ".X.O.", ".X.O.", ".X.O.", ".X.O."])
    state = new_game(5, 7, initial_board=board)
    own = _ownership(["++.--"] * 5)
    p = dame_fill(state, own)
    assert p is not None and p.x == 2
    settled = new_game(5, 7, initial_board=Board.from_rows([".XO.."] * 5))
    assert dame_fill(settled, _ownership(["++---"] * 5)) is None


def test_dame_fill_skips_unsafe_points() -> None:
    # The only neutral point (C5) is surrounded by White: no safe fill, so the bot may pass.
    board = Board.from_rows(["XO.O.", "OOOO.", ".....", ".....", "....."])
    state = new_game(5, 7, initial_board=board)
    own = _ownership(["++.--", "-----", "-----", "-----", "-----"])
    assert dame_fill(state, own) is None
