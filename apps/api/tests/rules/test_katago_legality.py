"""M1 acceptance: our rules engine agrees with KataGo on legality, point by point.

Fixtures are recorded by `scripts/record_legality_games.py` (random games through KataGo with its
legal-move mask at every turn). Each game is replayed through `ishi.rules`; every KataGo move must
be legal for us, and our legal set must equal KataGo's at every position.
"""

import json
from pathlib import Path

import pytest

from ishi.rules.coords import gtp_to_point, index_to_point, point_to_gtp
from ishi.rules.game import legal_moves, new_game, play

FIXTURES = sorted((Path(__file__).parents[1] / "fixtures" / "legality").glob("*.json"))


def test_twenty_games_recorded() -> None:
    assert len(FIXTURES) >= 20


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
def test_legality_matches_katago(path: Path) -> None:
    game = json.loads(path.read_text(encoding="utf-8"))
    size = game["size"]
    state = new_game(size, game["komi"])
    assert len(game["legal_masks"]) == len(game["moves"])
    for turn, ((color, move), mask) in enumerate(
        zip(game["moves"], game["legal_masks"], strict=True)
    ):
        assert state.to_move.value == color, f"turn {turn}: color mismatch"
        katago_legal = {index_to_point(i, size) for i, c in enumerate(mask) if c == "1"}
        ours = legal_moves(state)
        if ours != katago_legal:
            only_ours = sorted(point_to_gtp(p, size) for p in ours - katago_legal)
            only_kata = sorted(point_to_gtp(p, size) for p in katago_legal - ours)
            pytest.fail(
                f"turn {turn} ({color} to move): legal only for us {only_ours}, "
                f"only for KataGo {only_kata}\n" + "\n".join(state.board.to_rows())
            )
        state = play(state, gtp_to_point(move, size))
