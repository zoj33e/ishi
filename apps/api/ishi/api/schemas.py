"""Shared API response models (08-api-spec). Coordinates are GTP strings."""

from typing import Any, Literal

from pydantic import BaseModel

from ishi.rules.board import Color
from ishi.rules.coords import point_to_gtp
from ishi.rules.game import GameState
from ishi.rules.scoring import Score

ColorName = Literal["black", "white"]


def color_name(c: Color) -> ColorName:
    return "black" if c is Color.BLACK else "white"


class ErrorDetail(BaseModel):
    code: str
    message_key: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    """Every non-2xx response body (see `ishi.api.errors`)."""

    error: ErrorDetail


class Stones(BaseModel):
    black: list[str]
    white: list[str]


class Captures(BaseModel):
    black: int
    white: int


class GameStateOut(BaseModel):
    id: str
    mode: str
    board_size: int
    komi: float
    learner_color: ColorName
    to_move: ColorName
    stones: Stones
    last_move: str | None
    captures: Captures
    ko_point: str | None
    move_number: int
    status: Literal["active", "finished"]
    result: str | None
    nudges_left: int
    capture_target: int | None = None  # capture games: captures needed to win
    bot_level: int | None = None  # capture bot level
    exam_id: str | None = None


class ScoreOut(BaseModel):
    black_area: int
    white_area: int
    komi: float
    margin: float
    result: str
    territory: Stones  # empty points owned by each color (stones not repeated)


def game_state_out(
    state: GameState,
    *,
    id: str,
    mode: str,
    learner_color: Color = Color.BLACK,
    result: str | None = None,
    nudges_left: int = 0,
) -> GameStateOut:
    size = state.size
    last = state.last_move
    return GameStateOut(
        id=id,
        mode=mode,
        board_size=size,
        komi=state.komi,
        learner_color=color_name(learner_color),
        to_move=color_name(state.to_move),
        stones=Stones(
            black=[point_to_gtp(p, size) for p in state.board.stones(Color.BLACK)],
            white=[point_to_gtp(p, size) for p in state.board.stones(Color.WHITE)],
        ),
        last_move=point_to_gtp(last.point, size) if last else None,
        captures=Captures(black=state.captures_black, white=state.captures_white),
        ko_point=point_to_gtp(state.ko_point, size) if state.ko_point else None,
        move_number=state.move_number,
        status="finished" if state.is_over or result else "active",
        result=result,
        nudges_left=nudges_left,
    )


def score_out(score: Score, state: GameState) -> ScoreOut:
    size = state.size
    empty_owned = {
        c: [
            point_to_gtp(p, size)
            for p, owner in score.territory.items()
            if owner is c and state.board[p] is None
        ]
        for c in (Color.BLACK, Color.WHITE)
    }
    return ScoreOut(
        black_area=score.black_area,
        white_area=score.white_area,
        komi=score.komi,
        margin=score.margin,
        result=score.result,
        territory=Stones(black=empty_owned[Color.BLACK], white=empty_owned[Color.WHITE]),
    )
