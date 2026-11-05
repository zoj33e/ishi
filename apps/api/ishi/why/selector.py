"""Rank-aware filter and lesson selection: ONE lesson per game (05-why-engine, golden rule 4)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ishi.rules.board import Group
from ishi.rules.coords import Point, gtp_to_point, point_to_index
from ishi.why.context import ConceptHit, MoveContext
from ishi.why.detectors import UNEXPLAINED
from ishi.why.facts import cutting_points, groups_in_atari
from ishi.why.review import MoveReview

BELTS = ["white", "yellow", "orange", "green", "blue", "purple", "brown", "black"]
CONCEPT_BELT = {  # 02-curriculum: a concept is taught from this belt on
    "missed_capture": "yellow",
    "ignored_atari": "yellow",
    "self_atari": "yellow",
    "ladder": "orange",
    "cut_disconnect": "orange",
    "group_death": "green",
}
BELT_RANK = {"orange": 25.0, "green": 20.0, "blue": 15.0, "purple": 12.0, "brown": 10.0}
P_FIND_BELT = "orange"  # below this no HumanSL profile fits: skip the p_find check
MIN_P_FIND = 0.10
NEUTRAL_P_FIND = 0.5  # used in the score when p_find was skipped (D-038)
TARGET_STONES_STRONGER = 5
POINTS_CAP = 15.0
WEAK_CONCEPT_WEIGHT = 1.3
REPEAT_NOVELTY = 0.5


def belt_index(belt: str) -> int:
    return BELTS.index(belt)


def concept_unlocked(concept: str, belt: str) -> bool:
    need = CONCEPT_BELT.get(concept)
    return need is not None and belt_index(belt) >= belt_index(need)


def uses_p_find(belt: str) -> bool:
    return belt_index(belt) >= belt_index(P_FIND_BELT)


def learner_rank(belt: str, rank_estimate: float | None) -> float:
    if rank_estimate is not None:
        return rank_estimate
    return BELT_RANK.get(belt, 30.0)


def target_profile(rank: float) -> str:
    """HumanSL profile 5 stones stronger than the learner (rank_20k is the weakest there is)."""
    target = max(rank - TARGET_STONES_STRONGER, -8.0)
    if target >= 20:
        return "rank_20k"
    if target > 0:
        return f"rank_{round(target)}k"
    return f"rank_{1 - round(target)}d"


def p_find(human_policy: Sequence[float], correct_moves: Iterable[str], size: int) -> float:
    """How likely a slightly stronger player finds one of the correct moves."""
    total = 0.0
    for m in correct_moves:
        p = gtp_to_point(m, size)
        idx = len(human_policy) - 1 if p is None else point_to_index(p, size)
        total += max(0.0, human_policy[idx])
    return total


@dataclass(frozen=True)
class Candidate:
    review: MoveReview
    hit: ConceptHit
    p_find: float | None
    eligible: bool


def filter_hits(
    reviews: Sequence[MoveReview], belt: str, p_finds: dict[int, float | None]
) -> list[Candidate]:
    """Every concept hit with its readiness verdict (unexplained hits are never eligible)."""
    out = []
    for r in reviews:
        hit = r.hit
        if hit is None:
            continue
        pf = p_finds.get(r.number)
        ok = hit.concept_id != UNEXPLAINED and concept_unlocked(hit.concept_id, belt)
        if ok and uses_p_find(belt) and pf is not None and pf < MIN_P_FIND:
            ok = False
        out.append(Candidate(r, hit, pf, ok))
    return out


def weakest_concepts(recent_concepts: Sequence[str], n: int = 2) -> set[str]:
    counts = Counter(c for c in recent_concepts if c != UNEXPLAINED)
    return {c for c, _ in counts.most_common(n)}


def score(c: Candidate, weak: set[str], last_taught: str | None) -> float:
    pf = c.p_find if c.p_find is not None else NEUTRAL_P_FIND
    weight = WEAK_CONCEPT_WEIGHT if c.hit.concept_id in weak else 1.0
    novelty = REPEAT_NOVELTY if c.hit.concept_id == last_taught else 1.0
    return min(c.review.points_lost, POINTS_CAP) * (0.5 + pf) * weight * novelty


def pick_mistake(
    candidates: Sequence[Candidate], recent_concepts: Sequence[str], last_taught: str | None
) -> Candidate | None:
    eligible = [c for c in candidates if c.eligible]
    if not eligible:
        return None
    weak = weakest_concepts(recent_concepts)
    # max score; ties go to the earlier move
    return max(eligible, key=lambda c: (score(c, weak, last_taught), -c.review.number))


@dataclass(frozen=True)
class Praise:
    review: MoveReview
    kind: str  # "answered_atari" / "answered_cut"
    threat_move: str  # the opponent's move that made the threat
    group: Group  # the learner group that was threatened


def find_praise(reviews: Sequence[MoveReview]) -> Praise | None:
    """A learner move in KataGo's best set that answered a threat the opponent's move just made:
    an atari on a learner group, or a new cutting point. Biggest group wins, ties earlier."""
    found: list[Praise] = []
    for r in reviews:
        ctx = r.ctx
        if r.move not in ctx.best_moves or ctx.move is None:
            continue
        threat = ctx.state_before.last_move
        if threat is None or threat.point is None or threat.color is ctx.learner:
            continue
        board = ctx.board_before
        p = _answered_atari(ctx, threat.point)
        if p is not None:
            found.append(Praise(r, "answered_atari", ctx.gtp(threat.point), p))
            continue
        cuts = cutting_points(board, ctx.learner)
        near = [pt for pt in cuts if pt == threat.point or threat.point in board.neighbors(pt)]
        if near and any(ctx.move == pt or ctx.move in board.neighbors(pt) for pt in near):
            biggest = max((g for pt in near for g in cuts[pt]), key=lambda g: len(g.stones))
            found.append(Praise(r, "answered_cut", ctx.gtp(threat.point), biggest))
    if not found:
        return None
    return max(found, key=lambda p: (len(p.group.stones), -p.review.number))


def _answered_atari(ctx: MoveContext, threat: Point) -> Group | None:
    board = ctx.board_before
    for g in groups_in_atari(board, ctx.learner):
        if any(n == threat for s in g.stones for n in board.neighbors(s)):
            after = ctx.board_after.group_at(next(iter(g.stones)))
            if after is not None and len(after.liberties) >= 2:
                return g
    return None
