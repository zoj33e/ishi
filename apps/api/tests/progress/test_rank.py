"""Rank estimate (M8): likelihood interpolation, results model, blending, adaptive bot."""

from __future__ import annotations

import math
import random

import pytest

from ishi.progress import rank


def _parabola(peak: float) -> dict[float, float]:
    return {r: -((r - peak) ** 2) for r in rank.LIKELIHOOD_PROFILES.values()}


@pytest.mark.parametrize("peak", [16.0, 12.5, 9.0, 6.2, 3.0])
def test_likelihood_rank_finds_the_peak_between_profiles(peak: float) -> None:
    assert rank.likelihood_rank(_parabola(peak)) == pytest.approx(peak, abs=0.01)


def test_likelihood_rank_at_the_edges_and_without_data() -> None:
    assert rank.likelihood_rank(_parabola(27.0)) == 20.0
    assert rank.likelihood_rank(_parabola(-3.0)) == 0.0
    assert rank.likelihood_rank({20.0: -1.0, 15.0: -2.0}) is None


def test_win_probability_matches_the_9x9_calibration() -> None:
    assert rank.win_probability(15.0, 20.0) == pytest.approx(0.65, abs=0.01)  # 5 stones
    assert rank.win_probability(15.0, 15.0) == pytest.approx(0.5)


def test_results_rank_without_games_is_the_prior() -> None:
    assert rank.results_rank(25.0, []) == 25.0


@pytest.mark.parametrize("true", [24.0, 18.0, 12.0])
def test_results_rank_recovers_a_simulated_player(true: float) -> None:
    rng = random.Random(int(true))
    games = []
    for _ in range(2000):
        bot = true + rng.uniform(-10, 10)
        games.append((bot, rng.random() < rank.win_probability(true, bot)))
    assert rank.results_rank(25.0, games) == pytest.approx(true, abs=1.5)


def test_winning_moves_the_estimate_stronger() -> None:
    assert rank.results_rank(25.0, [(25.0, True)] * 3) < 25.0
    assert rank.results_rank(25.0, [(25.0, False)] * 3) > 25.0


def test_likelihood_certainty_comes_from_the_curvature() -> None:
    sharp = rank.likelihood_fit(
        {r: -4 * (r - 12.0) ** 2 for r in rank.LIKELIHOOD_PROFILES.values()}
    )
    flat = rank.likelihood_fit(
        {r: -0.01 * (r - 12.0) ** 2 for r in rank.LIKELIHOOD_PROFILES.values()}
    )
    assert sharp is not None and flat is not None
    assert sharp[1] == rank.MIN_LIKELIHOOD_SD**2 and flat[1] == pytest.approx(50.0)


def test_estimate_starts_from_the_likelihood_and_results_update_it() -> None:
    sure = {r: -2 * (r - 12.0) ** 2 for r in rank.LIKELIHOOD_PROFILES.values()}
    unsure = {r: -0.02 * (r - 12.0) ** 2 for r in rank.LIKELIHOOD_PROFILES.values()}
    losses = [(14.0, False)] * 8  # lost 8 games to a weaker bot
    a = rank.estimate(25.0, losses, sure, likelihood_moves=80)
    b = rank.estimate(25.0, losses, unsure, likelihood_moves=80)
    assert a.likelihood_rank == pytest.approx(12.0, abs=0.01)
    assert 12.0 < a.rank < b.rank  # results move a confident likelihood less
    assert a.results_rank == rank.results_rank(25.0, losses)  # results alone, for the chart
    none = rank.estimate(25.0, [], sure, likelihood_moves=80)
    assert none.rank == pytest.approx(12.0, abs=0.05)
    weak = rank.estimate(25.0, losses, _parabola(26.0), likelihood_moves=80)  # 20k or weaker
    assert weak.rank == weak.results_rank and weak.likelihood_rank == 20.0
    few = rank.estimate(25.0, losses, sure, likelihood_moves=5)
    assert few.rank == few.results_rank and few.likelihood_rank is None


def test_adaptive_bot_rank() -> None:
    assert rank.adaptive_bot_rank(20.0, []) == 21.0  # one stone easier
    assert rank.adaptive_bot_rank(20.0, [True, True]) == 21.0  # too few games to adapt
    assert rank.adaptive_bot_rank(20.0, [True] * 5 + [False]) == 20.0  # 83% wins: stronger
    assert rank.adaptive_bot_rank(20.0, [False] * 4 + [True] * 2) == 22.0  # 33%: weaker
    assert rank.adaptive_bot_rank(20.0, [True, False] * 3) == 21.0  # 50%: as is
    assert rank.adaptive_bot_rank(20.0, [False] * 10 + [True] * 6) == 20.0  # last 6 only
    assert rank.adaptive_bot_rank(35.0, []) == 30.0 and rank.adaptive_bot_rank(-12, []) == -8.0


def test_likelihood_is_unsure_when_the_weakest_profile_fits_best() -> None:
    # sharp curve, but the 20k profile scores best: the learner may be anywhere weaker
    fit = rank.likelihood_fit({r: -4 * (r - 18.0) ** 2 for r in rank.LIKELIHOOD_PROFILES.values()})
    assert fit is not None
    assert fit[0] == pytest.approx(18.0, abs=0.01) and fit[1] == rank.EDGE_LIKELIHOOD_SD**2


def test_policy_expected_logl() -> None:
    assert rank.policy_expected_logl([1.0, -1.0, 0.0]) == pytest.approx(0.0, abs=1e-5)
    two = rank.policy_expected_logl([0.5, 0.5, -1.0])
    assert two == pytest.approx(math.log(0.5), abs=1e-5)  # a coin flip
    assert rank.policy_expected_logl([-1.0, 0.0]) == 0.0


def test_weak_learners_are_placed_by_their_surprise() -> None:
    edge = {r: -((r - 22.0) ** 2) for r in rank.LIKELIHOOD_PROFILES.values()}  # 20k fits best
    plain = rank.estimate(25.0, [], edge, likelihood_moves=80)
    weak = rank.estimate(25.0, [], edge, likelihood_moves=80, surprise=1.0)
    assert plain.rank == 25.0  # "20k or weaker": the belt guess
    assert weak.rank == pytest.approx(rank.WEAK_RANK_AT_ZERO + rank.WEAK_STONES_PER_NAT, abs=0.05)
    assert weak.likelihood_rank == weak.rank
    typical = rank.estimate(25.0, [], edge, likelihood_moves=80, surprise=-0.2)
    assert typical.rank == 25.0  # moves as typical as a 20k player's: no weak-end reading
    stronger = {r: -((r - 12.0) ** 2) for r in rank.LIKELIHOOD_PROFILES.values()}
    assert rank.estimate(25.0, [], stronger, likelihood_moves=80, surprise=1.0).rank == (
        pytest.approx(12.0, abs=0.05)
    )
    assert rank.weak_rank(-5.0) == rank.LIKELIHOOD_FLOOR and rank.weak_rank(9.0) == rank.WEAK_MAX
