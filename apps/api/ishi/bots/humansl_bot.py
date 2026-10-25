"""HumanSL bot for full-rule games (M3). Pure functions; the KataGo I/O lives in `ishi.play`.

Strength scale (07-data-model): kyu as a float, 25k -> 25.0, 1d -> 0.0, 2d -> -1.0.
- 20k and stronger: KataGo's human model at that rank, sampled with temperature T = 0.8.
- Weaker than 20k (D-032, D-034): the 20k human model with T = 1.0-1.3 plus a "blunder" rate b: with
  probability b the move is picked uniformly from the 10 most human-likely moves.

Passing: only when the main search says the game is over (pass is KataGo's best move, or passing
loses < 0.5 points). Resigning: winrate < 3% on 3 bot turns in a row after move 20 (9x9).
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

PASS_INDEX = -1  # humanPolicy has size*size + 1 entries; the last one is pass
TOP_K_BLUNDER = 10
RESIGN_WINRATE = 0.03
RESIGN_STREAK = 3
RESIGN_AFTER_MOVE = 20
PASS_MARGIN = 0.5
BOT_VISITS = 40

# Blunder rates for the weak levels, tuned by scripts/calibrate_bots.py (docs/calibration-log.md).
WEAK_BLUNDER: dict[int, float] = {22: 0.06, 24: 0.15, 26: 0.28, 28: 0.45, 30: 0.7}
# Temperature eases from 1.3 toward 20k's 0.8 so 22k is not a cliff below 20k (D-034).
WEAK_TEMPERATURE: dict[int, float] = {22: 1.0, 24: 1.15, 26: 1.3, 28: 1.3, 30: 1.3}

# Ranks offered in the strength picker until adaptive strength arrives in M8 (D-031).
PICKER_RANKS: tuple[float, ...] = (
    30,
    28,
    26,
    24,
    22,
    20,
    18,
    15,
    12,
    10,
    8,
    5,
    3,
    1,
    0,
    -2,
    -4,
)


@dataclass(frozen=True)
class BotProfile:
    rank: float
    profile: str  # KataGo humanSLProfile
    temperature: float
    blunder: float


def rank_label(rank: float) -> str:
    """25.0 -> "25k", 0.0 -> "1d", -2.0 -> "3d"."""
    r = round(rank)
    return f"{r}k" if r >= 1 else f"{1 - r}d"


def profile_for(rank: float) -> BotProfile:
    r = round(rank)
    if r > 20:
        weak = min(WEAK_BLUNDER, key=lambda k: abs(k - r))
        return BotProfile(r, "rank_20k", WEAK_TEMPERATURE[weak], WEAK_BLUNDER[weak])
    if r < -8:
        raise ValueError(f"rank {rank} stronger than 9d")
    return BotProfile(r, f"rank_{rank_label(r)}", 0.8, 0.0)


def choose_index(
    human_policy: Sequence[float],
    legal: set[int],
    profile: BotProfile,
    rng: random.Random,
) -> int | None:
    """Pick a board index from the human policy (illegal entries are -1). None = no legal move."""
    cands = [(i, human_policy[i]) for i in sorted(legal) if human_policy[i] > 0]
    if not cands:
        # The policy can put ~0 on every legal move in rare endgame spots: play any legal move.
        return rng.choice(sorted(legal)) if legal else None
    if profile.blunder > 0 and rng.random() < profile.blunder:
        top = sorted(cands, key=lambda c: -c[1])[:TOP_K_BLUNDER]
        return rng.choice(top)[0]
    inv_t = 1.0 / profile.temperature
    weights = [math.exp(inv_t * math.log(p)) for _, p in cands]
    return rng.choices([i for i, _ in cands], weights=weights)[0]


@dataclass(frozen=True)
class SearchSummary:
    """The bits of a KataGo search the bot needs, already from the bot's point of view."""

    winrate: float
    best_move: str  # GTP or "pass"
    best_lead: float
    pass_lead: float | None  # scoreLead after passing, if KataGo searched it


def pass_ok(s: SearchSummary) -> bool:
    if s.best_move.lower() == "pass":
        return True
    return s.pass_lead is not None and s.best_lead - s.pass_lead < PASS_MARGIN


def next_resign_streak(streak: int, winrate: float, move_number: int) -> int:
    """Consecutive bot turns below the resign threshold (counted only after move 20)."""
    if move_number <= RESIGN_AFTER_MOVE or winrate >= RESIGN_WINRATE:
        return 0
    return streak + 1


def should_resign(streak: int) -> bool:
    return streak >= RESIGN_STREAK
