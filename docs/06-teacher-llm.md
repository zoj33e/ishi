# 06 — Teacher (narration layer)

Claude turns a `FactPackage` into a teacher's voice. It adds **tone and clarity, never facts**.

## Pipeline (`teacher/narrator.py`)
```
FactPackage → template narration (always)            ┐
FactPackage → Claude (if ISHI_LLM_ENABLED) → validate ├→ final Lesson
                     invalid / error → use template   ┘
```
Templates are the safety net and must alone produce an acceptable lesson in both languages. They live in `teacher/templates/{concept_id}.{th,en}.yaml` with slots like `{played_move}`, `{save_move}`, `{size}`.

## Model and cost
- Model: `claude-haiku-5-5` (env `ISHI_LLM_MODEL`).
- Use **prompt caching** on the system prompt + concept guide (static).
- Max output ~300 tokens. One call per lesson; nudges use templates by default (latency), LLM optional behind a flag.
- Cache final narration by `hash(FactPackage minus move_number)`; the same pattern reuses text.

## Output contract
The model must return **only JSON** (use structured outputs / tool-use JSON schema if available in the SDK):
```json
{
  "headline": "string, ≤ 12 words (Thai: ≤ 40 characters)",
  "explanation": ["sentence", "sentence"],
  "question": "string or null",
  "hints": ["level-1 question", "level-2 area hint"],
  "takeaway": "string, 1 sentence",
  "marks": [{"point": "E5", "kind": "circle|triangle|square|cross|label", "label": "A"}]
}
```
`explanation`: 2–4 sentences. `hints`: exactly 2 (level 3 = showing the move, done by the UI).

## Validator (`teacher/validator.py`) — reject if any:
- JSON doesn't parse or violates schema/length limits.
- Any coordinate pattern (`[A-HJ-T][1-9][0-9]?`) in any string or mark is not in `allowed_coordinates`.
- Mentions a concept name/keyword from the glossary that isn't `concept_id` or in `secondary_concepts` (keyword list per locale in `teacher/concept_keywords.yaml`).
- Contains numbers of points/stones not present in the package (allow `points_lost` rounded, group sizes).
- Wrong language (Thai locale must be mostly Thai script; English must be ASCII-dominant).
On reject: log the reason + raw output; use template. Track reject rate; > 10% means the prompt needs work.

## System prompt (store in `teacher/prompts/system.md`)
```
You are Ishi, a warm, patient Go teacher for a beginner.

You receive a FACT PACKAGE about one moment in the learner's game. It was
produced by a strong engine and a rule checker. It is the ONLY source of truth.

Rules:
- Use only facts in the package. Never invent moves, groups, outcomes,
  numbers, or reasons. Never judge positions yourself.
- Mention coordinates only from allowed_coordinates.
- Teach exactly one idea: concept_id. Do not mention secondary concepts.
- Plain words first, Go term second, e.g. "your stones can only breathe once
  more — this is called atari".
- If concept_is_new is true, define the term in one short clause.
- Ask the learner a question before revealing the answer when lesson_type is
  "mistake" or "nudge".
- For "nudge": do NOT reveal the correct move; only ask a guiding question.
- Be encouraging, never condescending. No exclamation spam. No emojis.
- Write in the language given by locale ("th" = natural spoken Thai a Go
  teacher would use with a teenager; "en" = simple English).
- Output only JSON matching the schema.
```
The user message is the FactPackage JSON plus the concept guide snippet for that concept (definition + 1 good example explanation per locale, from `teacher/prompts/concepts/{concept_id}.md`).

## Hint ladder (nudges and puzzles)
| Level | Content | Source |
|-------|---------|--------|
| 1 | Guiding question ("Count the liberties of your stones on the right.") | `hints[0]` / template |
| 2 | Area hint: highlight a 3x3 region around the key point + sentence | `hints[1]` / template |
| 3 | Show the move + follow-up line | UI, from package |

## Nudge rules
- Trigger: learner previews a move with pointsLost ≥ max(4, 2 × learner's median pointsLost in last 5 games), a detector fires, concept unlocked, rank filter passes.
- Budget: 2 nudges per game; 0 during belt exams.
- Learner can always "Play anyway". Then the move counts normally and can still become the lesson.
- Nudge text never reveals the answer.

## Praise
Praise packages use `lesson_type: "praise"`, include the threat the opponent made and the learner's correct answer. Narration: name what they did right in one sentence, why it worked in one sentence.

## Thai language notes
- Use the glossary terms in `12-glossary.md`; first mention in Thai may add the English/Japanese term in parentheses, e.g. "อาตาริ (atari)".
- Coordinates stay Latin (E5). Numbers as Arabic digits.
- Tone: friendly teacher (ครู), use "เรา/คุณ", avoid overly formal ครับ/ค่ะ every sentence; one polite particle at the end of the lesson is enough.

## Evaluation
`tests/teacher/eval_set/` holds 30 FactPackages (5 per MVP concept) with human-checked reference narrations. `scripts/eval_teacher.py` runs the model, the validator, and prints reject rate + outputs side by side for manual review. Run it whenever the prompt changes.
