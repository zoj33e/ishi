"""Pydantic models for the KataGo analysis engine protocol (verified against KataGo v1.18.1 docs).

Unknown fields are ignored; missing required fields raise.
All raw values are from Black's perspective (`reportAnalysisWinratesAs = BLACK`).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Player = Literal["B", "W"]


class KataRules(BaseModel):
    """Must match `ishi.rules` exactly (D-007)."""

    ko: str = "SIMPLE"
    scoring: str = "AREA"
    tax: str = "NONE"
    suicide: bool = False
    hasButton: bool = False
    whiteHandicapBonus: str = "0"
    friendlyPassOk: bool = True


class AnalysisQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    moves: list[tuple[Player, str]] = Field(default_factory=list)
    initialStones: list[tuple[Player, str]] | None = None
    initialPlayer: Player | None = None
    rules: KataRules = Field(default_factory=KataRules)
    komi: float = 7
    boardXSize: int = 9
    boardYSize: int = 9
    analyzeTurns: list[int] | None = None
    maxVisits: int | None = None
    includeOwnership: bool = False
    includePolicy: bool = False
    overrideSettings: dict[str, object] | None = None
    avoidMoves: list[dict[str, object]] | None = None
    allowMoves: list[dict[str, object]] | None = None
    priority: int = 0

    def expected_responses(self) -> int:
        return len(self.analyzeTurns) if self.analyzeTurns else 1


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class MoveInfo(_Lenient):
    move: str
    visits: int
    winrate: float
    scoreLead: float
    prior: float
    order: int
    pv: list[str] = Field(default_factory=list)
    humanPrior: float | None = None


class RootInfo(_Lenient):
    winrate: float
    scoreLead: float
    visits: int
    currentPlayer: Player


class AnalysisResponse(_Lenient):
    id: str
    turnNumber: int
    isDuringSearch: bool = False
    moveInfos: list[MoveInfo]
    rootInfo: RootInfo
    ownership: list[float] | None = None
    policy: list[float] | None = None
    humanPolicy: list[float] | None = None
