"""Per-move KataGo analysis of a game (M4): every position, 500 visits, ownership, low priority.

`analyses[t]` = KataGo's view of the position after t moves (t = 0: the empty board).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from ishi.engine.katago_process import KataGoProcess
from ishi.engine.models import AnalysisResponse
from ishi.engine.queries import POSTGAME_VISITS, game_analysis_query
from ishi.rules.game import GameState

log = logging.getLogger("ishi.analysis")

TURNS_PER_QUERY = 8
QUERY_TIMEOUT = 120.0  # seconds for one batch at low priority


async def analyze_positions(
    engine: KataGoProcess,
    state: GameState,
    turns: Iterable[int],
    *,
    qid: str,
    max_visits: int = POSTGAME_VISITS,
) -> dict[int, AnalysisResponse]:
    wanted = sorted(set(turns))
    batches = [wanted[i : i + TURNS_PER_QUERY] for i in range(0, len(wanted), TURNS_PER_QUERY)]

    async def one(i: int, batch: list[int]) -> list[AnalysisResponse]:
        query = game_analysis_query(f"{qid}-a{i}", state, batch, max_visits=max_visits)
        log.debug("analysis query %s turns %s", query.id, batch)
        return await engine.analyze(query, timeout=QUERY_TIMEOUT)

    results = await asyncio.gather(*(one(i, b) for i, b in enumerate(batches)))
    return {r.turnNumber: r for rs in results for r in rs}
