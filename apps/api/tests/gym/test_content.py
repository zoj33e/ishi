"""Seed puzzle content (M6): enough per concept, the built set matches the authored diagrams, and
every accepted answer really does what the concept asks."""

from collections import Counter

import pytest

from ishi.db.models import Puzzle
from ishi.gym import service as gym
from ishi.gym.puzzles import load_authored, load_seed, resolves
from ishi.rules.board import Color
from ishi.rules.coords import point_to_gtp
from ishi.why.selector import CONCEPT_BELT

MIN_PER_CONCEPT = 15
AUTHORED = {p.id: p for p in load_authored()}
SEED = {item["id"]: item for item in load_seed()}


def _puzzle(item: dict) -> Puzzle:
    return Puzzle(
        user_id="u",
        source="seed",
        seed_id=item["id"],
        concept_id=item["concept_id"],
        board_size=item["board_size"],
        setup=item["setup"],
        correct_moves=item["correct_moves"],
        solution_line=item["solution_line"],
        learner_moves=item["learner_moves"],
    )


def test_enough_puzzles_per_concept() -> None:
    counts = Counter(item["concept_id"] for item in SEED.values())
    assert set(counts) == set(CONCEPT_BELT)
    assert min(counts.values()) >= MIN_PER_CONCEPT, counts


def test_seed_matches_the_authored_diagrams() -> None:
    assert len(AUTHORED) == len(load_authored()), "duplicate ids"
    assert set(SEED) == set(AUTHORED), "run scripts/build_puzzles.py"
    for pid, pz in AUTHORED.items():
        item = SEED[pid]
        size = pz.size
        assert item["concept_id"] == pz.concept_id
        for color in (Color.BLACK, Color.WHITE):
            stones = [point_to_gtp(p, size) for p in pz.board.stones(color)]
            assert item["setup"]["black" if color is Color.BLACK else "white"] == stones
        assert item["setup"]["to_move"] == ("black" if pz.to_move is Color.BLACK else "white")
        assert item["setup"]["target"] == pz.target
        assert item["learner_moves"] == pz.moves
        assert pz.answer in item["correct_moves"]
        assert item["solution_line"][0].split()[-1] == pz.answer


@pytest.mark.parametrize("pid", sorted(AUTHORED))
def test_every_accepted_answer_solves(pid: str) -> None:
    pz = AUTHORED[pid]
    for move in SEED[pid]["correct_moves"]:
        assert resolves(pz, move) is not False, move  # group_death: checked by KataGo at build


@pytest.mark.parametrize("pid", sorted(p for p, item in SEED.items() if item["learner_moves"] > 1))
def test_chase_puzzles_can_be_finished(pid: str) -> None:
    """Play the answer, then keep chasing on the defender's last liberty: it ends solved."""
    puzzle = _puzzle(SEED[pid])
    moves = [puzzle.correct_moves[0]]
    for _ in range(puzzle.learner_moves):
        correct, done, reply = gym.grade(puzzle, moves)
        assert correct
        if done:
            return
        assert reply is not None
        state = gym.puzzle_state(puzzle)
        for m in [*moves, reply]:
            state = gym.play(state, gym._pt(m, puzzle.board_size))
        target = gym._pt(puzzle.setup["target"], puzzle.board_size)
        group = state.board.group_at(target)
        assert group is not None
        libs = [point_to_gtp(p, puzzle.board_size) for p in group.liberties]
        chase = [m for m in libs if gym.grade(puzzle, [*moves, reply, m])[0]]
        assert chase, f"no atari keeps the chase going after {[*moves, reply]}"
        moves += [reply, chase[0]]
    correct, done, _ = gym.grade(puzzle, moves)
    assert correct and done
