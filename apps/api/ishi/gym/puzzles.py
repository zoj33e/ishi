"""Shape Gym puzzles (02-curriculum): seed puzzle content, "does this move solve it" checks and the
FSRS rating rule. Pure functions, no I/O except reading the content files.

Seed puzzles are hand-authored diagrams in `content/puzzles/<concept>.yaml`; the build script
(`scripts/build_puzzles.py`) asks KataGo for the answer set and writes `content/puzzles/seed.json`,
which is what the app loads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from ishi.config import REPO_ROOT
from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, gtp_to_point, point_to_gtp
from ishi.rules.game import GameState, Legality, check_move, new_game, play
from ishi.why.ladder import read_ladder

PUZZLES_DIR = REPO_ROOT / "content" / "puzzles"
SEED_FILE = PUZZLES_DIR / "seed.json"
REGION_DISTANCE = 2  # answers are looked for within this many points of the puzzle's stones
KOMI = 7.0

Rating = Literal["again", "hard", "good", "easy"]
EASY_MS = 5000  # 02-curriculum: solved < 5 s = Easy
FAILED_TRIES = 2  # the second wrong move shows the answer (like the lesson retry, D-043)


# -- content -------------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedPuzzle:
    """One authored puzzle. `target` is a stone of the group the puzzle is about (the one to
    capture, save, or make alive); `cut_points` are the points a connect puzzle must cover."""

    id: str
    concept_id: str
    board: Board
    to_move: Color
    answer: str
    moves: int = 1  # learner moves to solve (the opponent answers in between)
    target: str | None = None
    cut_points: tuple[str, ...] = ()
    note: str = ""

    @property
    def size(self) -> int:
        return self.board.size

    def state(self) -> GameState:
        return new_game(self.size, KOMI, initial_board=self.board, to_move=self.to_move)

    def region(self) -> list[str]:
        return region(self.board)


def region(board: Board) -> list[str]:
    """Empty points within REGION_DISTANCE (Chebyshev) of any stone: where answers may be."""
    stones = [p for p in board.points() if board[p] is not None]
    out = []
    for p in board.points():
        if board[p] is None and any(
            max(abs(p.x - s.x), abs(p.y - s.y)) <= REGION_DISTANCE for s in stones
        ):
            out.append(point_to_gtp(p, board.size))
    return out


def load_authored(directory: Path = PUZZLES_DIR) -> list[SeedPuzzle]:
    puzzles = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        concept = data["concept"]
        for item in data["puzzles"]:
            puzzles.append(
                SeedPuzzle(
                    id=item["id"],
                    concept_id=concept,
                    board=_diagram(item["board"]),
                    to_move=Color.parse(item.get("to_move", "black")),
                    answer=item["answer"],
                    moves=item.get("moves", 1),
                    target=item.get("target"),
                    cut_points=tuple(item.get("cut_points", ())),
                    note=item.get("note", ""),
                )
            )
    return puzzles


def _diagram(text: str) -> Board:
    """A board diagram; `#` starts a comment (row numbers, column letters)."""
    return Board.from_rows(line.split("#")[0] for line in text.splitlines())


@lru_cache
def load_seed(path: Path = SEED_FILE) -> tuple[dict[str, Any], ...]:
    """The built seed set: `{id, concept_id, board_size, setup, correct_moves, solution_line,
    learner_moves}` per puzzle (setup as in `puzzles.setup`)."""
    return tuple(json.loads(path.read_text(encoding="utf-8")))


# -- does a first move solve the puzzle? ---------------------------------------------------


def _pt(gtp: str, size: int) -> Point:
    p = gtp_to_point(gtp, size)
    assert p is not None
    return p


def _target_libs(board: Board, target: Point) -> int | None:
    g = board.group_at(target)
    return None if g is None else len(g.liberties)


def resolves(puzzle: SeedPuzzle, move: str) -> bool | None:
    """Whether `move` does what the puzzle's concept asks, judged on the board alone.

    None = the board can't tell (group_death: life needs KataGo's ownership; the build script
    checks it). Multi-move capture puzzles are judged by reading the chase that follows."""
    state = puzzle.state()
    p = _pt(move, puzzle.size)
    if check_move(state, p) is not Legality.OK:
        return False
    after = play(state, p)
    board = after.board
    me = puzzle.to_move
    target = _pt(puzzle.target, puzzle.size) if puzzle.target else None
    concept = puzzle.concept_id
    if concept in ("missed_capture", "ladder"):
        assert target is not None
        if _target_libs(board, target) is None:  # captured
            return True
        if puzzle.moves == 1:
            return False
        # a chase: the move puts it in atari, and the chase that follows captures it
        before = _target_libs(puzzle.board, target) or 0
        return before >= 2 and chase_holds(board, target)
    if concept == "ignored_atari":
        assert target is not None
        return _safe(board, target)
    if concept == "self_atari":
        own = board.group_at(p)
        assert own is not None
        if len(own.liberties) < 2:
            return False
        return target is None or _safe(board, target)
    if concept == "cut_disconnect":
        return all(_covered(after, _pt(c, puzzle.size), me) for c in puzzle.cut_points)
    if concept == "group_death":
        return None
    raise ValueError(f"unknown concept {concept}")


def chase_holds(board: Board, target: Point) -> bool:
    """The chased chain is captured, or in atari with no escape (its ladder works)."""
    libs = _target_libs(board, target)
    return libs is None or (libs == 1 and read_ladder(board, target).works)


def defender_reply(board: Board, target: Point) -> Point | None:
    """The chased chain runs: it extends at its last liberty (None when captured or free)."""
    group = board.group_at(target)
    if group is None or len(group.liberties) != 1:
        return None
    return next(iter(group.liberties))


def _safe(board: Board, target: Point) -> bool:
    """The learner's group can't be captured right away: 3+ liberties, or 2 with no working
    ladder against it."""
    libs = _target_libs(board, target)
    if libs is None or libs < 2:
        return False
    return libs > 2 or not read_ladder(board, target).works


def _covered(state: GameState, cut: Point, me: Color) -> bool:
    """A cut point is covered when it is ours, or an opponent stone there would be captured at
    once (e.g. a tiger's mouth)."""
    board = state.board
    if board[cut] is me:
        return True
    if board[cut] is not None:
        return False
    their_turn = GameState(board=board, to_move=me.opponent, komi=state.komi)
    if check_move(their_turn, cut) is not Legality.OK:
        return True
    group = play(their_turn, cut).board.group_at(cut)
    return group is not None and len(group.liberties) <= 1


# -- rating --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    solved: bool
    wrong_tries: int = 0
    hints_used: int = 0
    time_ms: int | None = None


def rating(outcome: Outcome) -> Rating:
    """02-curriculum: first try without hints = Good; after a hint = Hard; failed = Again;
    solved < 5 s = Easy. A wrong try counts like a hint (the learner got feedback)."""
    if not outcome.solved:
        return "again"
    if outcome.hints_used > 0 or outcome.wrong_tries > 0:
        return "hard"
    if outcome.time_ms is not None and outcome.time_ms < EASY_MS:
        return "easy"
    return "good"
