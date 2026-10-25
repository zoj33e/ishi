"""Rules-school lesson format (YAML in `content/lessons/`), bilingual.

See content/lessons/README.md.

Every task is graded by the rules engine (`ishi.school.grading`); answers are never hard-coded
unless the concept itself needs an authored list (e.g. which stones are dead).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ishi.config import REPO_ROOT

LESSONS_DIR = REPO_ROOT / "content" / "lessons"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class L10n(_Strict):
    en: str
    th: str

    def get(self, locale: str) -> str:
        return self.th if locale == "th" else self.en


class Setup(_Strict):
    size: int | None = None  # defaults to the lesson's board_size
    black: list[str] = []
    white: list[str] = []
    to_move: Literal["black", "white"] = "black"
    moves: list[str] = []  # played from the setup (alternating, starting with to_move)
    komi: float = 0


class Mark(_Strict):
    point: str
    kind: Literal["circle", "triangle", "square", "cross", "label"]
    label: str | None = None


# -- goals for "play" tasks --------------------------------------------------------------


class PlaceAny(_Strict):
    type: Literal["place_any"]


class PlaceAt(_Strict):
    type: Literal["place_at"]
    points: list[str]


class Capture(_Strict):
    type: Literal["capture"]
    min_stones: int = 1
    target: str | None = None  # a stone that must be among the captured ones


class Atari(_Strict):
    type: Literal["atari"]
    target: str | None = None  # opponent stone whose chain must end with one liberty


class Escape(_Strict):
    type: Literal["escape"]
    target: str  # own stone whose chain must end with >= min_libs liberties
    min_libs: int = 2


class Connect(_Strict):
    type: Literal["connect"]
    a: str
    b: str


class Cut(_Strict):
    type: Literal["cut"]
    a: str  # two opponent stones in different chains
    b: str


class Pass(_Strict):
    type: Literal["pass"]


class TwoEyes(_Strict):
    type: Literal["two_eyes"]
    target: str


Goal = Annotated[
    PlaceAny | PlaceAt | Capture | Atari | Escape | Connect | Cut | Pass | TwoEyes,
    Field(discriminator="type"),
]


class Reply(_Strict):
    """Scripted opponent answer after a correct step."""

    type: Literal["fixed", "save_atari"]
    move: str | None = None  # for fixed
    target: str | None = None  # for save_atari: only save the chain holding this stone
    fallback: str = "pass"  # for save_atari when nothing is in atari


class Step(_Strict):
    goal: Goal
    reply: Reply | None = None


# -- what to count / select / choose -------------------------------------------------------


class CountSpec(_Strict):
    type: Literal["liberties", "area"]
    target: str | None = None  # liberties
    color: Literal["black", "white"] | None = None  # area
    dead: list[str] = []  # area


class SelectSpec(_Strict):
    type: Literal["liberties", "suicide_points", "ko_point", "false_eyes", "points"]
    target: str | None = None  # liberties / false_eyes
    points: list[str] = []  # authored set
    mode: Literal["one", "all"] = "all"  # tap one correct point, or exactly all of them


class ChooseSpec(_Strict):
    type: Literal["winner"]
    dead: list[str] = []


class Task(_Strict):
    id: str
    kind: Literal["play", "count", "select", "choose"]
    prompt: L10n
    hint: L10n
    success: L10n
    setup: Setup
    steps: list[Step] = []  # play
    count: CountSpec | None = None
    select: SelectSpec | None = None
    choose: ChooseSpec | None = None
    expect: int | str | None = None  # optional author's expected answer, checked by tests

    @model_validator(mode="after")
    def _kind_matches(self) -> Task:
        need = {
            "play": bool(self.steps),
            "count": self.count is not None,
            "select": self.select is not None,
            "choose": self.choose is not None,
        }
        if not need[self.kind]:
            raise ValueError(f"task {self.id}: kind {self.kind} needs its spec")
        if sum(need.values()) != 1:
            raise ValueError(f"task {self.id}: exactly one of steps/count/select/choose")
        return self


class DemoFrame(_Strict):
    text: L10n
    move: str | None = None  # played before showing this frame
    marks: list[Mark] = []


class Demo(_Strict):
    setup: Setup
    frames: list[DemoFrame] = Field(min_length=1)


class Lesson(_Strict):
    id: str
    order: int
    board_size: int
    title: L10n
    idea: L10n
    demo: Demo
    tasks: list[Task] = Field(min_length=2, max_length=4)
    takeaway: L10n

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)


@lru_cache
def load_lessons(directory: Path = LESSONS_DIR) -> tuple[Lesson, ...]:
    lessons = []
    for path in sorted(directory.glob("R*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        lessons.append(Lesson.model_validate(data))
    lessons.sort(key=lambda lesson: lesson.order)
    ids = [lesson.id for lesson in lessons]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate lesson ids: {ids}")
    return tuple(lessons)


def get_lesson(lesson_id: str) -> Lesson | None:
    return next((lesson for lesson in load_lessons() if lesson.id == lesson_id), None)
