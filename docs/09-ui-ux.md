# 09 — UI / UX

Mobile-first PWA (portrait phone is the main target), works on desktop. Calm, focused, one thing on screen at a time. Load the `frontend-design` guidance (if available) before building the visual style.

## Visual direction
- Feel: quiet study room. Warm kaya-wood board, soft paper background, ink-black and shell-white stones with subtle shadows.
- Teacher presence: a small circular avatar (simple original mark — a stone with a brush stroke), speech panel slides up from the bottom.
- Typography: a Thai-friendly font pair (e.g. `IBM Plex Sans Thai` + `IBM Plex Sans`), large readable sizes (body ≥ 16px).
- Colors as CSS tokens with light and dark themes. Mistake color scale: yellow (small) → orange → red (big).
- Motion: stones drop with a 120 ms ease; captures fade 200 ms; respect `prefers-reduced-motion`.

## Board component (`components/board/`)
- SVG, scales to container width; star points; optional coordinates (setting).
- Layers (bottom→top): wood, grid, stones, last-move marker, marks (circle/triangle/square/cross/label), ghost stone, highlight region (hint level 2), ownership heatmap (post-MVP).
- Input: **tap to place ghost, tap the same point again to confirm** (prevents mis-taps on phones; also triggers `preview`). Desktop: hover shows ghost, click confirms.
- Touch target: the full intersection cell; board min 9x9 at 340px wide.
- Read-only mode for lessons/demos; "replay line" mode animates a PV with step controls.
- Accessibility: every intersection has an aria-label ("E5, black stone"); keyboard arrow navigation + Enter.

## Screens
### 1. Onboarding
Language picker (ไทย / English) → teacher intro (2 lines) → start R1.

### 2. Home ("Today")
- Belt badge + rank estimate + streak.
- Primary card: "Start today's session" (warm-up → game → lesson as one guided flow).
- Secondary: Shape Gym, Rules school, Progress, Exam (only when available).

### 3. Rules school lesson
Step header (2/4) → teacher text → small board → task prompt → instant feedback (green check / gentle "try again" with hint button).

### 4. Game
- Board top, compact info row (captures, whose turn, nudges left as small dots), action bar: Pass, Resign, (Undo disabled outside capture practice).
- Nudge: teacher panel slides up over the bottom third, shows the question; buttons **Rethink** (removes ghost) / **Hint** / **Play anyway**.
- Bot "thinking" indicator if > 300 ms.
- Game over sheet: result, "See your lesson" button.

### 5. Lesson
- Board at the critical moment, learner's actual move shown as a faded stone with a red marker.
- Teacher panel: headline (bold), explanation sentences revealed one tap at a time, question.
- "Try it" → board becomes interactive → feedback → hint ladder → solution line replay.
- Takeaway + "Added to Shape Gym" chip → Done.

### 6. Shape Gym
Card stack UI: concept tag, "Black to play", board, hint button, timer hidden by default. After answer: result + next.

### 7. Progress
Rank line chart (rank_history), belt path, top concepts lost (simple bars; becomes Weakness DNA radar post-MVP).

### 8. Exam
Clear rules screen → 12 puzzles → best-of-3 games (no nudges) → result screen with belt animation on pass.

## Copy & i18n
- All strings in `messages/{th,en}.json`. Keys namespaced by screen (`game.nudge.playAnyway`).
- Thai copy written natively, not machine-translated literally; keep sentences short.
- Never show raw numbers like winrate to beginners. Points lost shown only as dot color + "big / medium / small mistake".

## States to design for
Engine offline banner; LLM offline (silent — templates take over); first-time empty states (no puzzles yet → seed set); offline PWA (show cached home + "connect to your PC to play").
