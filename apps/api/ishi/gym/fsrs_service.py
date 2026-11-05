"""FSRS scheduling for Shape Gym cards (02-curriculum, D-055).

Day-based: no same-day learning steps (a missed puzzle comes back tomorrow, not in 10 minutes) and
no fuzzing, so the schedule is deterministic. A card is due for the whole local day it falls on.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from fsrs import Card, Rating, Scheduler

from ishi.db.models import SrsCard
from ishi.gym.puzzles import Rating as RatingName

SCHEDULER = Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)
RATINGS: dict[RatingName, Rating] = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
}


def day_start(now: datetime) -> datetime:
    """Local midnight of `now`'s day (`now` must be timezone-aware)."""
    return datetime.combine(now.date(), time(), tzinfo=now.tzinfo)


def day_end(now: datetime) -> datetime:
    """The next local midnight: everything due before it is due today."""
    return day_start(now) + timedelta(days=1)


def new_card(user_id: str, puzzle_id: str, due: datetime) -> SrsCard:
    card = Card(due=due.astimezone(UTC))
    return SrsCard(
        user_id=user_id,
        puzzle_id=puzzle_id,
        fsrs_state=card.to_dict(),
        due_at=card.due,
        reps=0,
        lapses=0,
    )


def review(card: SrsCard, rating: RatingName, now: datetime) -> SrsCard:
    """Apply one review. A failed review of a card already learned counts as a lapse."""
    before = Card.from_dict(card.fsrs_state)
    after, _ = SCHEDULER.review_card(before, RATINGS[rating], now.astimezone(UTC))
    if rating == "again" and card.reps > 0:
        card.lapses += 1
    card.reps += 1
    card.fsrs_state = after.to_dict()
    card.due_at = after.due
    card.updated_at = now
    return card
