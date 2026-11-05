"""Query builders, perspective helpers, pointsLost and the best-move set."""

from ishi.engine.models import AnalysisQuery, AnalysisResponse, MoveInfo, Player
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


# -- per-move analysis (M4) ----------------------------------------------------------------

BEST_SET_VISIT_SHARE = 0.10
BEST_SET_MARGIN = 1.0  # points


def game_analysis_query(
    qid: str, state: GameState, turns: list[int], *, max_visits: int = POSTGAME_VISITS
) -> AnalysisQuery:
    """Analyze several positions of a game (turn t = after t moves) with ownership, also per
    candidate move (group_death's vital point needs it), at low priority. Setup positions (golden
    fixtures) are sent as `initialStones`."""
    initial, player = None, None
    if state.initial_board is not None:
        board = state.initial_board
        initial = [
            ("B" if board[p] is Color.BLACK else "W", point_to_gtp(p, state.size))
            for p in board.points()
            if board[p] is not None
        ]
        player = "B" if state.initial_player is Color.BLACK else "W"
    return AnalysisQuery(
        id=qid,
        moves=game_moves(state),
        initialStones=initial,
        initialPlayer=player,
        komi=state.komi,
        boardXSize=state.size,
        boardYSize=state.size,
        analyzeTurns=turns,
        maxVisits=max_visits,
        includeOwnership=True,
        includeMovesOwnership=True,
        priority=-10,
    )


def human_policy_query(qid: str, state: GameState, turns: list[int], profile: str) -> AnalysisQuery:
    """HumanSL policy only (1 visit) for the rank filter's p_find, at low priority."""
    return AnalysisQuery(
        id=qid,
        moves=game_moves(state),
        komi=state.komi,
        boardXSize=state.size,
        boardYSize=state.size,
        analyzeTurns=turns,
        maxVisits=1,
        includePolicy=True,
        overrideSettings={"humanSLProfile": profile},
        priority=-10,
    )


def top_move(resp: AnalysisResponse) -> MoveInfo:
    return min(resp.moveInfos, key=lambda m: m.order)


def best_lead(resp: AnalysisResponse, player: Color) -> float:
    """scoreLead of the top move, from `player`'s (the mover's) perspective."""
    return for_player(top_move(resp).scoreLead, player)


def points_lost(before: AnalysisResponse, after: AnalysisResponse, mover: Color) -> float:
    """bestScoreLead_before(mover) - scoreLead_after(mover), clamped at 0 (04-katago)."""
    return max(0.0, best_lead(before, mover) - for_player(after.rootInfo.scoreLead, mover))


def best_move_set(resp: AnalysisResponse, mover: Color) -> list[str]:
    """Moves with >= 10% of the top move's visits and within 1.0 point of its scoreLead."""
    top = top_move(resp)
    best = for_player(top.scoreLead, mover)
    return [
        m.move
        for m in sorted(resp.moveInfos, key=lambda m: m.order)
        if m.visits >= BEST_SET_VISIT_SHARE * top.visits
        and best - for_player(m.scoreLead, mover) <= BEST_SET_MARGIN
    ]


# -- Shape Gym (M6) ------------------------------------------------------------------------

PUZZLE_VISITS = 800


def puzzle_query(
    qid: str,
    state: GameState,
    region: list[str] | None,
    *,
    max_visits: int = PUZZLE_VISITS,
    moves_ownership: bool = False,
) -> AnalysisQuery:
    """Analyze a puzzle position (setup + moves so far). With a region, the side to move may only
    play there (`allowMoves`, first move only): a puzzle asks about one local fight, so a bigger
    move elsewhere on a sparse board must not crowd out the answer."""
    query = game_analysis_query(qid, state, [len(state.moves)], max_visits=max_visits)
    query.priority = 0
    query.includeOwnership = moves_ownership
    query.includeMovesOwnership = moves_ownership
    if region:
        player = "B" if state.to_move is Color.BLACK else "W"
        query.allowMoves = [{"player": player, "moves": region, "untilDepth": 1}]
    return query
