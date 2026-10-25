# 02 — Curriculum

Built for a **total beginner**. Grounded in how strong players are actually trained: heavy life-and-death (tactics) practice, lots of small fast games, reviewing your own mistakes, spaced repetition.

## Board progression
1. **Rules school** — tiny boards (5x5 to 7x7 diagrams).
2. **Capture Go** — 7x7 then 9x9, first capture wins (then first to 3 captures).
3. **Full 9x9** — real games, area scoring, komi 7.
4. **13x13** (post-MVP) — after Blue belt.
5. **19x19** (post-MVP) — after Purple belt.

> ⚠️ KataGo does **not** understand Capture Go rules. Capture Go uses Ishi's own tactical bot (see `04-katago-integration.md` → Capture Go bot). KataGo is only used for full-rule games.

## Belts
| Belt | Approx. rank | Board | Unlock / exam |
|------|--------------|-------|---------------|
| White | — | rules | Complete all rules lessons |
| Yellow | ~30k | Capture Go | Beat capture bot 3/5 games (first-to-3 captures) |
| Orange | 25k | 9x9 | Beat bot rank_25k-equivalent best-of-3 + 10/12 puzzles |
| Green | 20k | 9x9 | Beat rank_20k bot best-of-3 + 10/12 puzzles |
| Blue | 15k | 9x9 | Beat rank_15k bot best-of-3 + 10/12 puzzles |
| Purple | 12k | 9x9/13x13 | Beat rank_12k bot best-of-3 + 10/12 puzzles |
| Brown | 10k | 13x13 | Beat rank_10k bot best-of-3 + 10/12 puzzles |
| Black | 1d | 19x19 | Post-MVP |

Notes:
- HumanSL profiles start at `rank_20k` (verify). Below that, the weaker bots come from HumanSL `rank_20k` with higher softmax temperature plus a random "blunder" rate; calibrate them against the capture bot and against the learner's results. Record the calibration in `13-decisions.md`.
- Exam unlock criteria: estimated rank within 2 stones of the next belt AND ≥ 5 games played since last belt.
- Failing an exam: retry allowed after 3 more games.

## Rules school (White belt)
Each lesson: 1-sentence idea → 1 demo → 2–4 interactive tasks. All tasks auto-graded by the rules engine.

| # | Lesson | Tasks |
|---|--------|-------|
| R1 | The board & taking turns | Place stones on intersections; black first |
| R2 | Liberties (ลมหายใจ) | Count liberties of 1 stone, a chain, edge/corner stones |
| R3 | Capture | Capture a single stone; capture a chain |
| R4 | Atari & escape | Find atari; save a stone by extending |
| R5 | Connect & cut | Connect two stones; find the cut |
| R6 | Illegal moves | Suicide is illegal; except when it captures |
| R7 | Ko | Why you can't retake immediately; play a ko threat |
| R8 | Eyes & life | Two eyes live; one eye dies; false eye (intro) |
| R9 | Territory & counting | Area scoring on a finished 5x5/7x7; komi idea |
| R10 | Ending the game | Passing, dead stones, scoring summary |

## Concept catalog
Each concept has: id, belt it is introduced at, detector (see `05-why-engine.md`), lesson template, and puzzle tags.

### MVP concepts (6)
| ID | Concept | Introduced | Plain explanation |
|----|---------|-----------|-------------------|
| C1 | `missed_capture` | Yellow | You could have captured stones but didn't. |
| C2 | `ignored_atari` | Yellow | Your stones were in atari and you didn't save them. |
| C3 | `self_atari` | Yellow | Your move put your own stones in atari. |
| C4 | `ladder` | Orange | A chase that captures along a diagonal (or a broken ladder you tried). |
| C5 | `cut_disconnect` | Orange | You left a cut / your opponent separated your stones. |
| C6 | `group_death` | Green | A group lost its life because a vital point was missed. |

### Post-MVP concepts (planned)
`net` (geta), `snapback`, `shortage_of_liberties`, `false_eye`, `eye_shape_vital_point`, `overextension`, `too_slow_small_move`, `big_point_missed`, `endgame_size`, `capturing_race` (semeai), `ko_fight`, `first_line_too_early`.

### Concept order of teaching
A concept can only be taught (lesson or nudge) once the learner's belt ≥ its introduced belt. Before that, mistakes of that concept are skipped silently (they may still lose the game — that's fine).

## Daily session composition
| Block | Rule |
|-------|------|
| Warm-up | All due Shape Gym cards, capped at 8. If fewer than 3 due, top up with puzzles of the learner's weakest concept. |
| Game | 1 game. Board and bot rank follow the belt table; bot rank = estimated learner rank minus 1 stone (slightly easier, to keep win rate ~55%). |
| Lesson | 1 lesson from that game (see selection in `05-why-engine.md`). If the game has no teachable mistake: a "good move" praise moment instead. |

Adaptive bot rank: after each game, if learner win rate over last 6 games > 65%, bot +1 stone; < 40%, bot −1 stone.

## Puzzles (Shape Gym)
- Source A: **the learner's own mistakes** (critical position, correct move set from KataGo).
- Source B: **seed puzzle set** per concept (hand-authored SGF in `content/puzzles/`, at least 15 per MVP concept). Required because a beginner hasn't made enough mistakes yet.
- Correct answers: any move within 1.0 point of the best (9x9) counts as correct, provided it also resolves the concept (e.g., actually captures). Multi-move puzzles: KataGo plays the opponent's reply.
- Scheduling: FSRS. Rating from outcome: solved first try without hints = Good; solved after hint = Hard; failed = Again; solved < 5 s = Easy.

## Lesson anatomy (what the learner sees)
1. Board jumps to the critical moment (the position before the mistake).
2. **Headline** (≤ 12 words): e.g., "Your three stones could only breathe once."
3. **Explanation** (2–4 short sentences), with board marks.
4. **Question** before the answer when possible: "Where could you have saved them?"
5. **Retry:** learner plays; feedback; if fail twice, show the move and the follow-up line (max 6 moves).
6. **Takeaway** (1 sentence) + "Added to Shape Gym".
