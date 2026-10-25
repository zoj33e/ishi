# 11 — Testing

## Principles
- Pure logic (rules, detectors, selector, scheduler math) = fast unit tests, no engine, no network.
- KataGo is mocked in unit tests via **recorded fixtures**; real-engine tests are marked `@pytest.mark.engine` and run on the PC only.
- The LLM is never called in unit tests; validator and narrator are tested with canned model outputs.

## Layers
| Layer | Tool | What |
|-------|------|------|
| Rules engine | pytest | legality, captures, ko, suicide, scoring, SGF round-trip, coordinate conversion (incl. no `I` column) |
| Engine adapter | pytest + fixtures | parsing, perspective conversion, pointsLost, best-move set |
| Why Engine | pytest golden tests | each detector: positives + look-alike negatives |
| Ladder reader | pytest | working ladders, broken by breaker, broken by capture, edge cases |
| Selector & filter | pytest | scoring, novelty, unlock gating, praise fallback |
| Teacher | pytest | validator rejects bad coords/concepts/numbers/language; template rendering both locales |
| FSRS / gym | pytest + frozen time | due dates, ratings mapping |
| API | pytest + httpx TestClient | contracts match OpenAPI; error shape |
| Web | vitest | board component input (ghost → confirm), i18n keys exist in both locales |
| E2E | Playwright (mobile viewport) | onboarding → rules lesson → capture game → 9x9 game → lesson → gym |
| Engine integration | pytest `-m engine` | real KataGo: query round trip, HumanSL profiles, bot move latency |

## Golden test format (`tests/golden/{concept_id}/{case}/`)
```
position.sgf           # game up to and including the learner move
analysis_before.json   # recorded KataGo response
analysis_after.json
expected.json          # {"fires": true, "concept_id": "...", "key_points": {...}} or {"fires": false}
notes.md               # why this case exists (one line)
```
`scripts/record_fixture.py position.sgf` records the KataGo responses once; tests never hit the engine.

## Required negative cases (examples)
- `ignored_atari`: abandoning a group is actually the best move (sacrifice).
- `self_atari`: throw-in / snapback that KataGo rates as best.
- `missed_capture`: capturing is legal but loses (e.g., capturing into a snapback).
- `ladder`: ladder that looks broken but the breaker is ineffective.
- `cut_disconnect`: cut exists but both sides are independently alive.
- `group_death`: ownership swing caused by the opponent's previous move, not the learner's.

## Coverage targets
rules ≥ 95%, why ≥ 90%, teacher validator 100% of branches; others pragmatic.

## Manual QA per milestone
Play 3 games on the phone, read every lesson, write down anything confusing in `docs/qa-log.md`.
