"""The teacher's output contract (06-teacher-llm): what a lesson says and which marks it shows."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MarkKind = Literal["circle", "triangle", "square", "cross", "label"]


class Mark(BaseModel):
    model_config = ConfigDict(extra="forbid")

    point: str
    kind: MarkKind
    label: str | None = None


class Narration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headline: str
    explanation: list[str]
    question: str | None = None
    hints: list[str] = Field(default_factory=list)
    takeaway: str
    marks: list[Mark] = Field(default_factory=list)

    def texts(self) -> list[str]:
        """Every learner-visible string (for the validator)."""
        out = [self.headline, *self.explanation, *self.hints, self.takeaway]
        if self.question:
            out.append(self.question)
        out += [m.label for m in self.marks if m.label]
        return out


# JSON schema for structured outputs: every field required, no extras. Length limits are checked
# by the validator (structured outputs don't enforce them).
NARRATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "explanation": {"type": "array", "items": {"type": "string"}},
        "question": {"type": ["string", "null"]},
        "hints": {"type": "array", "items": {"type": "string"}},
        "takeaway": {"type": "string"},
        "marks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "point": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["circle", "triangle", "square", "cross", "label"],
                    },
                    "label": {"type": ["string", "null"]},
                },
                "required": ["point", "kind", "label"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "explanation", "question", "hints", "takeaway", "marks"],
    "additionalProperties": False,
}
