"""Rank estimate (04-katago-integration, M8). Pure functions, no I/O.

Ranks are kyu numbers that go below zero for dan: 25k -> 25.0, 1d -> 0.0, 3d -> -2.0. A bigger
number is a weaker player.

Two signals:
- likelihood: which HumanSL profile best predicts the learner's own moves (summed log-policy of
  the moves they played), interpolated with a parabola through the best profile and its
  neighbors; the parabola's curvature says how sure it is;
- results: wins and losses against bots of known rank (a one-parameter logistic model, i.e. Elo
  in stones, calibrated on 9x9 bot matches).

They are combined by certainty (D-064, replacing the spec's fixed 0.6 / 0.4): the likelihood
estimate is the starting point with its own uncertainty and the results update it. On 9x9 a game
result says little (5 stones stronger wins only ~66%), so the likelihood leads. HumanSL has no
profile below 20k: when the likelihood says "20k or weaker", the belt is the starting point and
the results decide.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

# profiles queried for the likelihood (the spec's list), and their rank
LIKELIHOOD_PROFILES: dict[str, float] = {
    "rank_20k": 20.0,
    "rank_15k": 15.0,
    "rank_10k": 10.0,
    "rank_5k": 5.0,
    "rank_1d": 0.0,
}
SKIP_OPENING = 4  # the first moves of a game say little about strength
RECENT_GAMES = 10  # likelihood window
RESULT_GAMES = 20  # results window
MIN_LIKELIHOOD_MOVES = 20  # fewer learner moves: no likelihood yet
LIKELIHOOD_FLOOR = 20.0  # "20k or weaker": the likelihood can't tell, use results only
EPS = 1e-6

# logistic scale in stones, from the 9x9 calibration (docs/calibration-log.md): 20k vs 15k and
# 15k vs 10k end ~65 / 35, i.e. 5 stones ~ ln(65/35) logits
STONE = 8.0
PRIOR_SD = 6.0  # stones; the belt is only a rough guess
MIN_LIKELIHOOD_SD = 1.0  # never trust the likelihood more than this
# a player weaker than 20k still plays most like the 20k profile (there is none below), so when
# that profile fits best the likelihood can't tell 18k from 25k: let the results decide more
EDGE_LIKELIHOOD_SD = 5.0
GRID = (-9.0, 40.0, 0.05)  # 9d .. 40k

BELT_PRIOR = {
    "white": 30.0,
    "yellow": 30.0,
    "orange": 25.0,
    "green": 20.0,
    "blue": 15.0,
    "purple": 12.0,
    "brown": 10.0,
    "black": 0.0,
}

# adaptive bot (02-curriculum)
BOT_EASIER = 1.0  # the bot plays one stone below the estimate
ADAPT_GAMES = 6
ADAPT_MIN_GAMES = 3
ADAPT_HIGH = 0.65  # winning more: one stone stronger
ADAPT_LOW = 0.40  # winning less: one stone weaker
BOT_RANK_RANGE = (-8.0, 30.0)  # 9d .. the weakest calibrated bot


def move_logl(policy: Sequence[float], index: int) -> float:
    """log P(the learner's move) under one profile's policy."""
    return math.log(max(policy[index], 0.0) + EPS)


# below 20k (D-066): the 20k profile is the weakest there is, so compare the learner's moves
# with what a typical 20k player would play there: the policy's own expected log-likelihood
EDGE_PROFILE = "rank_20k"
EDGE_EXPECTED_KEY = "rank_20k_expected"
# surprise = how much less likely, per move, the learner's moves are than a typical 20k player's
# (nats). Calibrated on the weak bots (scripts/rank_simulation.py, seed 11, 8 games per rank,
# 30k..20k): rank ~ 21.2 + 5.5 * surprise, residual sd ~1 stone
WEAK_RANK_AT_ZERO = 21.2
WEAK_STONES_PER_NAT = 5.5
WEAK_SD = 2.5  # 10 games are noisy (per-game sd ~0.5 nats) and the bots are only a proxy
WEAK_MAX = 35.0


def policy_expected_logl(policy: Sequence[float]) -> float:
    """E[log P(move)] when the move is drawn from the policy itself (illegal entries are < 0)."""
    total = sum(p for p in policy if p > 0)
    if total <= 0:
        return 0.0
    return sum((p / total) * math.log(p / total + EPS) for p in policy if p > 0)


def likelihood_fit(logl: Mapping[float, float]) -> tuple[float, float] | None:
    """Max-likelihood rank and its variance (stones²) from a parabola through the best profile
    and its neighbors (the two next to it at an edge).

    `logl` maps a profile's rank to the summed log-likelihood of the learner's moves."""
    if len(logl) < 3:
        return None
    ranks = sorted(logl)
    best = max(range(len(ranks)), key=lambda i: logl[ranks[i]])
    mid = min(max(best, 1), len(ranks) - 2)
    x0, x1, x2 = ranks[mid - 1 : mid + 2]
    y0, y1, y2 = (logl[x] for x in (x0, x1, x2))
    denom = (x0 - x1) * (x0 - x2) * (x1 - x2)
    a = (x2 * (y1 - y0) + x1 * (y0 - y2) + x0 * (y2 - y1)) / denom
    b = (x2 * x2 * (y0 - y1) + x1 * x1 * (y2 - y0) + x0 * x0 * (y1 - y2)) / denom
    if a >= 0:  # flat or upside down: no peak to read
        return ranks[best], PRIOR_SD**2
    peak = min(max(-b / (2 * a), ranks[0]), ranks[-1])
    floor_sd = EDGE_LIKELIHOOD_SD if best == len(ranks) - 1 else MIN_LIKELIHOOD_SD
    return peak, max(-1.0 / (2 * a), floor_sd**2)


def weak_rank(surprise: float) -> float:
    """Rank below 20k from the per-move surprise under the 20k profile."""
    return min(max(WEAK_RANK_AT_ZERO + WEAK_STONES_PER_NAT * surprise, LIKELIHOOD_FLOOR), WEAK_MAX)


def likelihood_rank(logl: Mapping[float, float]) -> float | None:
    fit = likelihood_fit(logl)
    return None if fit is None else fit[0]


def win_probability(learner: float, bot: float) -> float:
    """The learner's chance to beat a bot of rank `bot` (bigger rank = weaker)."""
    return 1.0 / (1.0 + math.exp(-(bot - learner) / STONE))


def results_rank(
    prior: float, games: Sequence[tuple[float, bool]], prior_sd: float = PRIOR_SD
) -> float:
    """The rank that best explains (bot rank, learner won) results, starting from the prior."""
    lo, hi, step = GRID
    best_r, best_v = prior, -math.inf
    for i in range(round((hi - lo) / step) + 1):
        r = lo + i * step
        v = -((r - prior) ** 2) / (2 * prior_sd**2)
        for bot, won in games:
            p = win_probability(r, bot)
            v += math.log(p if won else 1.0 - p)
        if v > best_v:
            best_r, best_v = r, v
    return round(best_r, 2)


@dataclass(frozen=True)
class RankEstimate:
    rank: float
    likelihood_rank: float | None
    results_rank: float
    games: int


def estimate(
    prior: float,
    results: Sequence[tuple[float, bool]],
    logl: Mapping[float, float],
    likelihood_moves: int,
    surprise: float | None = None,
) -> RankEstimate:
    """`prior` is the belt's rank; `results` are (bot rank, learner won) pairs; `surprise` is
    the per-move surprise under the 20k profile (None for games recorded before D-066)."""
    r = results_rank(prior, results)  # results alone, from the belt (shown on the chart)
    fit = likelihood_fit(logl) if likelihood_moves >= MIN_LIKELIHOOD_MOVES else None
    lk = None if fit is None else fit[0]
    weakest = fit is not None and max(logl, key=lambda k: logl[k]) == max(logl)
    if fit is not None and weakest and surprise is not None and surprise > 0:
        # the 20k profile fits best and the moves are less typical than a 20k player's
        lk = weak_rank(surprise)
        rank = results_rank(lk, results, prior_sd=WEAK_SD)
    elif fit is None or fit[0] >= LIKELIHOOD_FLOOR:
        rank = r
    else:
        rank = results_rank(fit[0], results, prior_sd=math.sqrt(fit[1]))
    return RankEstimate(round(rank, 2), None if lk is None else round(lk, 2), r, len(results))


def adaptive_bot_rank(rank: float, recent_wins: Sequence[bool]) -> float:
    """One stone easier than the learner, then a stone up or down by the last games' win rate.

    `recent_wins` holds the learner's last non-exam full games, newest last."""
    bot = rank + BOT_EASIER
    window = list(recent_wins)[-ADAPT_GAMES:]
    if len(window) >= ADAPT_MIN_GAMES:
        rate = sum(window) / len(window)
        if rate > ADAPT_HIGH:
            bot -= 1
        elif rate < ADAPT_LOW:
            bot += 1
    lo, hi = BOT_RANK_RANGE
    return float(min(max(round(bot), lo), hi))
