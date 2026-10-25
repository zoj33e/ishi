import random

import pytest

from ishi.bots.capture_bot import (
    CaptureBot,
    capture_over,
    capture_result,
    capture_winner,
)
from ishi.rules.board import Color
from ishi.rules.coords import point_to_gtp
from ishi.rules.game import GameState, legal_moves, new_game, play
from tests.rules.helpers import moves, position


def _move(bot: CaptureBot, state: GameState) -> str:
    return point_to_gtp(bot.choose(state), state.size)


@pytest.mark.parametrize("level", [1, 2, 3])
def test_captures_when_possible(level: int) -> None:
    s = position(
        [
            ".....",
            "..X..",
            ".XO..",
            "..X..",
            ".....",
        ]
    )
    bot = CaptureBot(level, target=1, rng=random.Random(0))
    assert _move(bot, s) == "D3"


@pytest.mark.parametrize("level", [1, 2, 3])
def test_takes_the_largest_capture(level: int) -> None:
    s = position(
        [
            "OX...",
            ".....",
            "...XX",
            "..XOO",
            "...X.",
        ]
    )
    bot = CaptureBot(level, target=5, rng=random.Random(0))
    assert _move(bot, s) == "E1"


def test_escapes_from_atari() -> None:
    s = position(
        [
            ".....",
            "..O..",
            ".OX..",
            "..O..",
            ".....",
        ]
    )
    bot = CaptureBot(3, target=1, rng=random.Random(0))
    assert _move(bot, s) == "D3"


def test_level3_avoids_self_atari_next_to_enemy() -> None:
    # Black must not play into a point where White captures at once.
    s = position(
        [
            ".....",
            ".....",
            "..O..",
            ".O.O.",
            ".....",
        ]
    )
    bot = CaptureBot(3, target=1, rng=random.Random(0))
    for seed in range(5):
        bot.rng = random.Random(seed)
        assert _move(bot, s) != "C2"


def test_passes_only_without_legal_moves() -> None:
    s = position(["XXX", "X.X", "XXX"])  # filling the last eye would be suicide
    assert legal_moves(s) == set()
    assert CaptureBot(1, target=1).choose(s) is None


def test_two_passes_end_the_game() -> None:
    s = moves(new_game(5, 0), "pass", "pass")
    assert capture_over(s, 1)
    assert capture_winner(s, 1) is None
    assert capture_result(s, 1) == "Draw"


def test_first_capture_wins() -> None:
    s = moves(new_game(5, 0), "B5", "A5")
    assert not capture_over(s, 1)
    s = moves(s, "A4")
    assert capture_winner(s, 1) is Color.BLACK
    assert capture_result(s, 1) == "B+C"
    # Not at the target yet: two passes give the win to whoever captured more.
    s2 = moves(s, "pass", "pass")
    assert capture_winner(s2, 3) is Color.BLACK


def _vs_random(level: int, size: int, target: int, bot_color: Color, seed: int) -> Color | None:
    rng = random.Random(seed)
    bot = CaptureBot(level, target, rng=random.Random(seed + 10_000))
    s = new_game(size, 0)
    for _ in range(400):
        if capture_over(s, target):
            break
        if s.to_move is bot_color:
            m = bot.choose(s)
        else:
            legal = sorted(legal_moves(s))
            m = rng.choice(legal) if legal else None
        s = play(s, m)
    return capture_winner(s, target)


def test_level1_beats_random_mover_95_percent() -> None:
    """M2 acceptance: 200 games, colors alternating, 9x9 first capture wins."""
    wins = 0
    for i in range(200):
        color = Color.BLACK if i % 2 == 0 else Color.WHITE
        wins += _vs_random(1, 9, 1, color, i) is color
    assert wins >= 190, f"level 1 won only {wins}/200"
