"""Query builders. Derived metrics (pointsLost, best-move set, perspective) land in M4."""

from ishi.engine.models import AnalysisQuery


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
