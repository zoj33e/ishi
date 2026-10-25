# 01 — Product PRD

## Vision
A patient Go teacher in your pocket. KataGo knows the right move; Ishi explains **why**, at your level, in Thai or English, and drills your weaknesses until they're gone.

## Primary user (MVP)
- **The builder himself.** Total beginner, Thai speaker, comfortable in English, plays on phone and PC.
- Wants to become a solid player fast, studying ~20 minutes a day.

Secondary (post-MVP): Thai/SEA beginners and school Go clubs.

## Success metric
- **North star:** learner's estimated rank over time.
- **Target hypothesis:** total beginner → 15k in 60 days, → 10k in 120 days, at ~20 min/day. Treat as a hypothesis; measure it.
- Supporting: daily streak, puzzles solved, % of lessons where the learner fixes the same mistake in a later game.

## Core loop (daily session, ~20 min)
1. **Warm-up (5 min):** Shape Gym puzzles due today (spaced repetition).
2. **Play (10 min):** one game vs a humanlike bot at the learner's level (9x9 after the rules stage).
3. **Lesson (5 min):** exactly one lesson from that game, chosen by the rank-aware filter, explained by the teacher, ending with a retry of the critical moment. The mistake becomes a new Shape Gym card.

## Features

### MVP (must have)
| ID | Feature | Summary |
|----|---------|---------|
| F1 | Rules school | Interactive lessons: placing stones, liberties, capture, illegal suicide, ko, counting. |
| F2 | Capture Go | First-capture-wins mini game vs a simple tactical bot. Gate to real games. |
| F3 | Play vs humanlike bot | 9x9 vs KataGo HumanSL bot at a chosen rank. |
| F4 | Why Engine | Deterministic detectors label mistakes with concepts (6 MVP concepts). |
| F5 | Teacher lesson | One lesson per game, narrated by Claude from facts, with board marks and a retry. |
| F6 | Socratic nudge | In-game: before a big blunder is confirmed, the teacher asks a question. Max 2 per game. Hint ladder: question → highlight area → show move. |
| F7 | Shape Gym | Mistakes become puzzles with spaced repetition (FSRS). |
| F8 | Belt progression | Belts with exams (bot best-of-3 + puzzle set). |
| F9 | Rank estimate | HumanSL likelihood + game results estimate the learner's rank. |
| F10 | Bilingual | Thai and English UI and narration, switchable anytime. |
| F11 | PWA | Installable on phone; backend runs on the home PC. |

### Post-MVP (designed for, not built)
| ID | Feature | Summary |
|----|---------|---------|
| P1 | Weakness DNA | Skill radar from concept-tagged mistakes. |
| P2 | Hunter Bot | Bot steers games toward the learner's weak concepts. |
| P3 | Three-player replay | "You / typical player at your rank / dan player" at key moments. |
| P4 | X-ray fade | Territory heatmap help that fades as rank rises. |
| P5 | Variant generation | Mirrored/shifted/reworded puzzle variants. |
| P6 | 13x13 and 19x19 | Bigger boards after 9x9 mastery. |
| P7 | Cloud + multi-user | Hosted engine, accounts, teacher dashboard. |
| P8 | Voice teacher | TTS narration. |

## Non-goals (MVP)
- Online play vs humans.
- Joseki/opening libraries.
- Pro game database.
- Payments, accounts, social features.
- Letting the LLM play or evaluate moves.

## Key user flows
1. **First launch:** choose language → rules school lesson 1 → 2 → … → Capture Go → first 9x9 game.
2. **Daily session:** Home shows "Today: 6 puzzles, 1 game" → warm-up → game → lesson → summary (streak, rank trend).
3. **Mid-game nudge:** learner places a ghost stone → backend finds a big teachable mistake → teacher asks a question → learner rethinks or insists → game continues.
4. **Lesson:** board jumps to the critical moment → teacher explains (headline, 2–4 sentences, marks) → "Try again" retry → success/fail feedback → card added to Shape Gym.
5. **Belt exam:** unlocks when criteria met → puzzle set → bot best-of-3 → pass = new belt + harder bot.

## Teaching principles (product behavior)
- Explain in plain words first, jargon second ("this group can only breathe once more — that's called atari").
- Ask before telling. The learner should find the move when possible.
- Praise good moves sometimes, specifically ("You saved your stones by connecting — exactly right").
- Never more than one new concept per lesson.
- Mistakes the learner isn't ready for are silently skipped.

## Constraints
- Runs on Windows PC with RTX 3070 Ti. Phone reaches it over Tailscale.
- LLM cost target: < $3/month for one daily user.
- Lesson generation latency: < 4 s after game end. Nudge latency: < 1.5 s.
