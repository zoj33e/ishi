# Media for the README

The README references these files. Until each one exists, its `<img>` tag stays commented out in `README.md` and `README.th.md`. Uncomment it once the file is here.

| File | Status |
|---|---|
| `logo.png` | done (app icon `apps/web/public/icons/icon-512.png` with the background removed) |
| `social-preview.png` | done (1280×640, upload in repo Settings → Social preview) |
| `demo.gif` | to capture |
| `play.png` | to capture |
| `lesson.png` | to capture |
| `progress.png` | to capture |

## Capture settings

- Use the **production build** (`scripts\start.ps1`, not `-Dev`) so there's no Next.js dev overlay.
- Use the **English** UI for the main README. For the Thai README, capture the same shots in Thai and save them with a `-th` suffix (e.g. `play-th.png`).
- Use a profile with a few games played, so the progress chart has real data.
- Hide the browser chrome: capture only the page.

## Screenshots: `play.png`, `lesson.png`, `progress.png`

All three sit side by side in one table row, so they must be **the same size and orientation**.

- Viewport: **390 × 844** (phone, portrait), device pixel ratio 2 → PNG **780 × 1688**.
- In Chrome/Edge DevTools: device toolbar → set 390 × 844, DPR 2 → ⋮ → "Capture screenshot".
- Keep each file under 1 MB (run through TinyPNG or `oxipng` if needed).

| File | What's on screen |
|---|---|
| `play.png` | A 9×9 game in the middle game (about move 20–30), with an **in-game nudge** open: the teacher's question visible above or below the board. |
| `lesson.png` | The post-game lesson: the board with the mistake and the better move marked, and the narrated explanation below it. Pick a lesson with a clear concept (missed capture or ladder read well). |
| `progress.png` | The progress screen: rank estimate chart with at least 5–6 points, and the belt path showing the current belt. |

## Demo GIF: `demo.gif`

Shown full width under the header, so use **landscape**.

- Length **≤ 25 s**, file size **≤ 8 MB**.
- Record at 1280 × 800, export at **800 px wide**, 12–15 fps. Trim pauses.
- Tools: ScreenToGif (Windows) records and exports directly; or record with OBS and convert:
  `ffmpeg -i demo.mp4 -vf "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" demo.gif`
- Storyboard:
  1. (0–6 s) Last few moves of a 9×9 game; the learner plays a mistake.
  2. (6–10 s) Game ends, "lesson ready" appears.
  3. (10–20 s) The lesson: board highlights the mistake, explanation text appears.
  4. (20–25 s) The learner replays the critical moment and plays the right move.
