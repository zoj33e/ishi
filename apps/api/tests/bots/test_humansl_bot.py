import random
from collections import Counter

import pytest

from ishi.bots.humansl_bot import (
    BotProfile,
    SearchSummary,
    choose_index,
    next_resign_streak,
    pass_ok,
    profile_for,
    rank_label,
    should_resign,
)


def test_rank_labels() -> None:
    assert rank_label(25) == "25k"
    assert rank_label(1) == "1k"
    assert rank_label(0) == "1d"
    assert rank_label(-2) == "3d"


def test_profiles() -> None:
    assert profile_for(15) == BotProfile(15, "rank_15k", 0.8, 0.0)
    assert profile_for(0).profile == "rank_1d"
    weak = profile_for(30)
    assert weak.profile == "rank_20k" and weak.temperature >= 1.0 and weak.blunder > 0
    blunders = [profile_for(r).blunder for r in (22, 24, 26, 28, 30)]
    assert blunders == sorted(blunders), "weaker levels blunder more"
    with pytest.raises(ValueError):
        profile_for(-9)


def _policy(values: dict[int, float], n: int = 81) -> list[float]:
    return [values.get(i, 0.0) for i in range(n)] + [0.0]


def test_choose_only_legal_and_follows_policy() -> None:
    pol = _policy({10: 0.7, 20: 0.2, 30: 0.1})
    p = BotProfile(10, "rank_10k", 0.8, 0.0)
    rng = random.Random(1)
    picks = Counter(choose_index(pol, {10, 20, 30, 40}, p, rng) for _ in range(2000))
    assert set(picks) <= {10, 20, 30}
    assert picks[10] > picks[20] > picks[30]
    # Illegal by our rules even if the policy likes it.
    assert all(choose_index(pol, {20, 30}, p, rng) in (20, 30) for _ in range(100))


def test_low_temperature_sharpens() -> None:
    pol = _policy({1: 0.6, 2: 0.4})
    rng = random.Random(2)
    cold = Counter(
        choose_index(pol, {1, 2}, BotProfile(5, "rank_5k", 0.3, 0), rng) for _ in range(2000)
    )
    hot = Counter(
        choose_index(pol, {1, 2}, BotProfile(5, "rank_5k", 2.0, 0), rng) for _ in range(2000)
    )
    assert cold[1] / 2000 > 0.75 > hot[1] / 2000


def test_blunders_pick_from_top_ten() -> None:
    pol = _policy({i: 1.0 / (i + 1) for i in range(30)})
    p = BotProfile(30, "rank_20k", 1.3, 1.0)  # always blunder
    rng = random.Random(3)
    picks = {choose_index(pol, set(range(30)), p, rng) for _ in range(500)}
    assert picks == set(range(10))


def test_no_policy_mass_falls_back_to_any_legal() -> None:
    p = BotProfile(10, "rank_10k", 0.8, 0)
    assert choose_index(_policy({}), {5}, p, random.Random(0)) == 5
    assert choose_index(_policy({}), set(), p, random.Random(0)) is None


def test_pass_rule() -> None:
    assert pass_ok(SearchSummary(0.5, "pass", 3, None))
    assert pass_ok(SearchSummary(0.5, "C3", 3.0, 2.7))
    assert not pass_ok(SearchSummary(0.5, "C3", 3.0, 2.0))
    assert not pass_ok(SearchSummary(0.5, "C3", 3.0, None))


def test_resign_rule() -> None:
    s = 0
    for move in (18, 19, 20):  # too early: never counts
        s = next_resign_streak(s, 0.01, move)
    assert s == 0
    for move in (22, 24, 26):
        s = next_resign_streak(s, 0.01, move)
    assert should_resign(s)
    assert next_resign_streak(2, 0.2, 30) == 0  # a good turn resets the streak
