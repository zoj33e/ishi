"""Load Why Engine golden cases (tests/golden/{concept}/{case}/, see 11-testing)."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ishi.engine.models import AnalysisResponse
from ishi.rules.sgf import parse_sgf
from ishi.why.context import MoveContext

GOLDEN = Path(__file__).resolve().parents[1] / "golden"


@dataclass(frozen=True)
class GoldenCase:
    concept: str
    name: str
    path: Path
    ctx: MoveContext
    expected: dict[str, Any] | None  # None until expected.json is written

    @property
    def id(self) -> str:
        return f"{self.concept}/{self.name}"


def load_case(path: Path) -> GoldenCase:
    """position.sgf = setup stones + moves; its last move is the learner's."""
    game = parse_sgf((path / "position.sgf").read_text(encoding="utf-8"))
    *earlier, (_, move) = game.moves
    ctx = MoveContext(
        state_before=replace(game, moves=tuple(earlier)).to_state(),
        move=move,
        before=_analysis(path / "analysis_before.json"),
        after=_analysis(path / "analysis_after.json"),
    )
    exp = path / "expected.json"
    expected = json.loads(exp.read_text(encoding="utf-8")) if exp.exists() else None
    return GoldenCase(path.parent.name, path.name, path, ctx, expected)


def _analysis(path: Path) -> AnalysisResponse:
    return AnalysisResponse.model_validate_json(path.read_text(encoding="utf-8"))


def all_cases() -> list[GoldenCase]:
    return [load_case(p.parent) for p in sorted(GOLDEN.glob("*/*/position.sgf"))]
