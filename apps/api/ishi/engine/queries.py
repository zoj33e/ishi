"""Query builders and perspective helpers. pointsLost and the best-move set land in M4."""

from ishi.engine.models import AnalysisQuery, Player
from ishi.rules.board import Color
from ishi.rules.coords import point_to_gtp
from ishi.rules.game import GameState


def empty_board_query(qid: str, size: int = 9, max_visits: int = 100) -> AnalysisQuery:
    """Smoke-test query: analyze the empty board. Used by health checks and engine tests."""
    return AnalysisQuery(
        id=qid,
        moves=[],
        boardXSize=size,
        boardYSize=size,
        komi=7,
        analyzeTurns=[0],
        maxVisits=max_visits,
        includeOwnership=True,
        includePolicy=True,
    )


# -- full games (M3) ---------------------------------------------------------------------

POSTGAME_VISITS = 500


def game_moves(state: GameState) -> list[tuple[Player, str]]:
    """The game's moves in KataGo form (`[["B","E5"], ["W","pass"], ...]`)."""
    size = state.size
    return [
        ("B" if m.color is Color.BLACK else "W", point_to_gtp(m.point, size)) for m in state.moves
    ]


def position_query(
    qid: str,
    state: GameState,
    *,
    max_visits: int,
    human_profile: str | None = None,
    ownership: bool = False,
) -> AnalysisQuery:
    """Analyze the current position of a game that started from an empty board."""
    if state.initial_board is not None:
        raise ValueError("position_query needs a game that started from an empty board")
    return AnalysisQuery(
        id=qid,
        moves=game_moves(state),
        komi=state.komi,
        boardXSize=state.size,
        boardYSize=state.size,
        analyzeTurns=[len(state.moves)],
        maxVisits=max_visits,
        includeOwnership=ownership,
        includePolicy=human_profile is not None,
        overrideSettings={"humanSLProfile": human_profile} if human_profile else None,
    )


def for_player(value_black: float, player: Color) -> float:
    """A Black-perspective score lead converted to `player`'s perspective."""
    return value_black if player is Color.BLACK else -value_black


def winrate_for(winrate_black: float, player: Color) -> float:
    return winrate_black if player is Color.BLACK else 1.0 - winrate_black
