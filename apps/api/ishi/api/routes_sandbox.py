"""Debug: local two-player sandbox (M1). Stateless — the client sends the whole move list and the
backend rules engine replays it, so legality is always decided server-side."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ishi.api.errors import ApiError
from ishi.api.schemas import (
    ErrorResponse,
    GameStateOut,
    ScoreOut,
    game_state_out,
    score_out,
)
from ishi.rules.coords import gtp_to_point, point_to_gtp
from ishi.rules.game import IllegalMoveError, legal_moves, new_game, play
from ishi.rules.scoring import area_score
from ishi.rules.sgf import to_sgf

router = APIRouter()


class SandboxRequest(BaseModel):
    board_size: int = Field(default=9, ge=5, le=19)
    komi: float = 7
    moves: list[str] = Field(default_factory=list, max_length=1000)


class SandboxState(BaseModel):
    state: GameStateOut
    legal_moves: list[str]
    score: ScoreOut | None  # area score of the current board (no dead-stone removal)
    sgf: str


@router.post(
    "/sandbox/state", response_model=SandboxState, responses={422: {"model": ErrorResponse}}
)
def sandbox_state(req: SandboxRequest) -> SandboxState:
    size = req.board_size
    state = new_game(size, req.komi)
    for i, move in enumerate(req.moves, start=1):
        try:
            point = gtp_to_point(move, size)
        except ValueError:
            raise ApiError(
                422, "BAD_COORDINATE", "errors.bad_coordinate", {"move_number": i, "point": move}
            ) from None
        try:
            state = play(state, point)
        except IllegalMoveError as e:
            raise ApiError(
                422,
                "ILLEGAL_MOVE",
                "errors.illegal_move",
                {"move_number": i, "point": move, "reason": e.reason.value},
            ) from None
    score = area_score(state.board, state.komi)
    result = score.result if state.is_over else None
    return SandboxState(
        state=game_state_out(state, id="sandbox", mode="sandbox", result=result),
        legal_moves=sorted(point_to_gtp(p, size) for p in legal_moves(state)),
        score=score_out(score, state),
        sgf=to_sgf(state, result=result),
    )
