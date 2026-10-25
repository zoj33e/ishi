"""Every feedback key the grader can return must have text in the web app (rule 8: bilingual)."""

import json
import re
from pathlib import Path

import pytest

from ishi.config import REPO_ROOT
from ishi.rules.game import Legality

GRADING = Path(__file__).parents[2] / "ishi" / "school" / "grading.py"
MESSAGES = REPO_ROOT / "apps" / "web" / "messages"


def _feedback_keys() -> set[str]:
    src = GRADING.read_text(encoding="utf-8")
    keys = set(re.findall(r'FB \+ \(?"([a-z_]+)"', src))
    keys |= {k for pair in re.findall(r'"([a-z_]+)" if \w+ else "([a-z_]+)"', src) for k in pair}
    keys |= {f"illegal.{r.value}" for r in Legality if r is not Legality.OK}
    return keys


@pytest.mark.parametrize("locale", ["en", "th"])
def test_feedback_keys_have_text(locale: str) -> None:
    msgs = json.loads((MESSAGES / f"{locale}.json").read_text(encoding="utf-8"))
    feedback = msgs["school"]["feedback"]
    keys = _feedback_keys()
    assert {"correct", "keep_going", "wrong_count", "wrong_select"} <= keys
    for key in keys:
        node = feedback
        for part in key.split("."):
            assert part in node, f"{locale}: school.feedback.{key} missing"
            node = node[part]
        assert isinstance(node, str) and node
