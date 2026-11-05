from dataclasses import replace

import pytest

from ishi.engine.models import AnalysisResponse
from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, gtp_to_point
from ishi.rules.game import GameState, new_game, play
from ishi.why.context import MoveContext
from ishi.why.detectors import classify
from ishi.why.fact_package import learner_info, mistake_package, praise_package
from ishi.why.review import MoveReview
from ishi.why.selector import (
    Candidate,
    concept_unlocked,
    filter_hits,
    find_praise,
    p_find,
    pick_mistake,
    target_profile,
)

from .golden import GOLDEN, load_case


def _review(case: str, number: int = 1) -> MoveReview:
    ctx = load_case(GOLDEN / case).ctx
    return MoveReview(number, ctx.gtp(ctx.move), ctx.points_lost, classify(ctx), ctx)


def test_concept_unlock_by_belt() -> None:
    assert not concept_unlocked("self_atari", "white")
    assert concept_unlocked("self_atari", "yellow")
    assert not concept_unlocked("ladder", "yellow")
    assert concept_unlocked("ladder", "orange")
    assert not concept_unlocked("group_death", "orange")
    assert not concept_unlocked("unexplained", "black")


@pytest.mark.parametrize(
    ("rank", "profile"), [(30, "rank_20k"), (25, "rank_20k"), (20, "rank_15k"), (5, "rank_1d")]
)
def test_target_profile_is_five_stones_stronger(rank: float, profile: str) -> None:
    assert target_profile(rank) == profile


def test_p_find_sums_the_correct_moves() -> None:
    policy = [0.0] * 82
    policy[40] = 0.3  # E5 on 9x9
    policy[81] = 0.1  # pass
    assert p_find(policy, ["E5", "pass"], 9) == pytest.approx(0.4)
    assert p_find(policy, ["A1"], 9) == 0.0


def test_filter_hits_unlock_and_p_find() -> None:
    r = _review("self_atari/two_stones")
    assert r.hit is not None and r.hit.concept_id == "self_atari"
    [c] = filter_hits([r], "white", {})
    assert not c.eligible  # not unlocked at White belt
    [c] = filter_hits([r], "yellow", {})
    assert c.eligible and c.p_find is None  # below Orange: no p_find check
    [c] = filter_hits([r], "orange", {1: 0.05})
    assert not c.eligible  # too advanced: p_find < 0.10
    [c] = filter_hits([r], "orange", {1: 0.3})
    assert c.eligible


def test_pick_mistake_scores_and_novelty() -> None:
    a = _review("self_atari/two_stones", 5)  # ~12 points lost
    b = _review("ladder/ran_into", 9)  # ~6 points lost
    ca = Candidate(a, a.hit, None, True)  # type: ignore[arg-type]
    cb = Candidate(b, b.hit, None, True)  # type: ignore[arg-type]
    assert pick_mistake([ca, cb], [], None) is ca
    # Taught last time: novelty halves its score (12.4 * 0.5 = 6.2), still just above 5.9...
    assert pick_mistake([ca, cb], [], "self_atari") is ca
    # ...and the learner's weakest concept gets a 1.3 boost.
    assert pick_mistake([ca, cb], ["ladder", "ladder"], "self_atari") is cb
    assert pick_mistake([replace(ca, eligible=False)], [], None) is None


def test_mistake_package_coordinates() -> None:
    r = _review("self_atari/two_stones", 17)
    assert r.hit is not None
    pkg = mistake_package(
        r, r.hit, locale="th", learner=learner_info("yellow", None), concept_is_new=True
    )
    assert pkg.lesson_type == "mistake" and pkg.concept_id == "self_atari"
    assert pkg.played_move == "E5" and pkg.move_number == 17
    assert pkg.key_points["last_liberty"] == "D4"
    assert pkg.follow_up_line[0].startswith("W ")
    for c in [pkg.played_move, *pkg.correct_moves, *pkg.key_points.values()]:
        assert c in pkg.allowed_coordinates
    for g in pkg.groups:
        assert set(g.stones) <= set(pkg.allowed_coordinates)
    assert "PASS" not in pkg.allowed_coordinates


def _praise_board() -> tuple[GameState, AnalysisResponse]:
    """White's D4 ataris Black's D5 stone; Black answers E5 (KataGo's only candidate)."""
    e = "........."
    board = Board.from_rows([e, e, e, "...O.....", "..OX.....", e, e, e, e])
    state = play(new_game(9, 7, initial_board=board, to_move=Color.WHITE), _pt("D4"))  # atari
    resp = AnalysisResponse.model_validate(
        {
            "id": "x",
            "turnNumber": 1,
            "moveInfos": [
                {
                    "move": "E5",
                    "visits": 100,
                    "winrate": 0.5,
                    "scoreLead": 1,
                    "prior": 0.5,
                    "order": 0,
                }
            ],
            "rootInfo": {"winrate": 0.5, "scoreLead": 1, "visits": 100, "currentPlayer": "B"},
        }
    )
    return state, resp


def _review_praise_board() -> MoveReview:
    state, resp = _praise_board()
    return MoveReview(2, "E5", 0.0, None, MoveContext(state, _pt("E5"), resp, resp))


def test_praise_for_answering_an_atari() -> None:
    state, resp = _praise_board()
    praise = find_praise([_review_praise_board()])
    assert praise is not None and praise.kind == "answered_atari" and praise.threat_move == "D4"
    pkg = praise_package(praise, locale="en", learner=learner_info("yellow", None))
    assert pkg.lesson_type == "praise"
    assert {"D4", "E5", "D5"} <= set(pkg.allowed_coordinates)
    # A move outside KataGo's best set earns no praise.
    other = MoveContext(state, _pt("A1"), resp, resp)
    assert find_praise([MoveReview(2, "A1", 0.0, None, other)]) is None


def _pt(s: str) -> Point:
    p = gtp_to_point(s, 9)
    assert p is not None
    return p
