# 04 — KataGo Integration

> Field names below match KataGo's analysis engine as of mid-2026 to the best of our knowledge. **Before coding, read `docs/analysis_engine.md` and the human-model example configs from the installed KataGo release and correct this file if anything differs.**

## Setup
1. Download the latest KataGo Windows release. For the RTX 3070 Ti: start with the **OpenCL** build (no CUDA toolkit needed). Try **CUDA/TensorRT** later only if speed is a problem.
2. Download networks into `engine/models/`:
   - **Main net** for analysis: latest recommended b18 (or the 9x9-finetuned net for 9x9 games; benchmark both, keep the one with better 9x9 accuracy at our visit budget).
   - **HumanSL net:** `b18c384nbt-humanv0` (human imitation, conditioned on rank).
3. Run the benchmark once: `katago benchmark -model <main>` and set `numSearchThreads` from its recommendation.
4. Launch:
```
katago analysis -config engine/analysis.cfg -model <main> -human-model <humansl>
```
5. `scripts/setup_engine.ps1` must automate steps 2–4 and write `.env`.

### analysis.cfg essentials
```
reportAnalysisWinratesAs = BLACK
numAnalysisThreads = 4
numSearchThreadsPerAnalysisThread = <from benchmark>
nnMaxBatchSize = 64
```
All winrate / scoreLead / ownership values are therefore **from Black's perspective**. The adapter converts them to "from the mover's perspective" before anything else touches them.

## Rules (must match `rules/` engine exactly)
Send rules as an explicit object on every query:
```json
{"ko":"SIMPLE","scoring":"AREA","tax":"NONE","suicide":false,"hasButton":false,"whiteHandicapBonus":"0","friendlyPassOk":true}
```
- Komi: **7** on 9x9 (and 7 on 13x13/19x19 until decided otherwise).
- Coordinates: GTP style, columns `A`–`T` skipping `I`, rows from bottom (`A1` bottom-left). 9x9 uses `A B C D E F G H J`. `pass` for passes.
- The internal representation is `(x, y)` with `x=0` left, `y=0` top. `rules/coords.py` owns all conversions; nothing else converts coordinates.

## Query shape
```json
{
  "id": "g42-t17-analysis",
  "moves": [["B","E5"],["W","D4"]],
  "rules": { ... },
  "komi": 7,
  "boardXSize": 9,
  "boardYSize": 9,
  "analyzeTurns": [2],
  "maxVisits": 400,
  "includeOwnership": true,
  "includePolicy": true,
  "priority": 0
}
```
Optional fields we use: `overrideSettings` (HumanSL profile, see below), `avoidMoves`/`allowMoves` (puzzles), `initialStones` + `initialPlayer` (puzzles and rules-school positions).

## Response fields we depend on
- `moveInfos[]`: `move`, `visits`, `winrate`, `scoreLead`, `prior`, `order`, `pv[]`, `humanPrior` (when human model loaded).
- `rootInfo`: `winrate`, `scoreLead`, `visits`, `currentPlayer`.
- `ownership[]`: length `boardXSize*boardYSize`, row-major from the top-left, values in [-1, 1], Black-positive under our config.
- `policy[]` / `humanPolicy[]`: length `x*y+1` (last = pass), row-major from top-left, `-1` for illegal.

Pydantic models for all of these live in `engine/models.py`. Unknown fields are ignored; missing required fields raise.

## Derived metrics (computed in `engine/queries.py`)
- **scoreLead(mover)**: `scoreLead` converted to the mover's perspective.
- **pointsLost(move)** = `bestScoreLead_before(mover) − scoreLead_after(mover)`, where `before` is the root analysis of the position where the move was played and `after` is the root analysis of the resulting position (perspective converted). Clamp at ≥ 0.
- **Best move set**: all `moveInfos` with `visits ≥ 10%` of top move's visits and `scoreLead` within 1.0 point of the best.
- **Ownership by group**: average ownership over a group's stones (mover perspective). Used by `group_death`.

Visit budgets (9x9):
| Use | maxVisits |
|-----|-----------|
| Live position analysis (nudges) | 300 |
| Post-game per-move analysis | 500 |
| Puzzle answer generation | 1000 |
| Bot move (HumanSL) | 1–40, see bot section |

## HumanSL usage
Profiles are passed via `overrideSettings`:
```json
"overrideSettings": {"humanSLProfile": "rank_15k"}
```
Valid amateur profiles: `rank_20k` … `rank_1k`, `rank_1d` … `rank_9d` (verify list in the installed docs). With `includePolicy: true` the response contains `humanPolicy[]` for that profile.

We use HumanSL for three things:
1. **Bot moves** — what a player of rank R would play.
2. **Rank-aware filter** — would a player slightly stronger than the learner find the right move? (`05-why-engine.md`)
3. **Rank estimate** — which profile best predicts the learner's moves? (below)

## HumanSL bot (`bots/humansl_bot.py`)
Research finding: sampling from the human policy with a **softmax temperature** between argmax and raw sampling hits a target strength better than either extreme.
```
p_i ∝ humanPolicy_i ^ (1 / T)
```
- Default `T = 0.8`; tune per rank during calibration.
- Exclude illegal moves; exclude pass unless the main analysis says the game is over (both sides' best move is pass or `scoreLead` change of passing < 0.5).
- For ranks below `rank_20k` (Orange belt): use `rank_20k`, `T = 1.3`, plus blunder rate `b` (probability of picking uniformly from the top-10 human moves). Calibrate `b` so the bot loses ~45% vs a just-graduated Yellow belt.
- Bot must **resign** when `winrate(bot) < 3%` for 3 consecutive turns after move 30 (9x9: after move 20).
- `scripts/calibrate_bots.py`: run bot-vs-bot matches between adjacent ranks (≥ 50 games) and log win rates; adjacent ranks should be roughly 60/40.

## Rank estimate (`progress/rank.py`)
For each learner move in the last N=10 games (excluding the first 4 moves of each game):
- Query the position with several profiles (`rank_20k`, `rank_15k`, `rank_10k`, `rank_5k`, `rank_1d`) — batch them as separate queries with low priority.
- `logL(profile) = Σ log(humanPolicy_profile[move] + 1e-6)`.
- Interpolate the max-likelihood rank between neighboring profiles (fit a parabola over the 3 best).
- Blend with game results: `rank = 0.6 * likelihood_rank + 0.4 * results_rank`, where `results_rank` comes from a simple Elo update vs bot ranks.
- Below 20k, likelihood is unreliable; use results only (Capture Go and low-rank bot outcomes).
- Store daily snapshot in `rank_history`.

## Capture Go bot (`bots/capture_bot.py`) — no KataGo
Rules: normal Go legality, **game ends at first capture** (or first to K captures). Bot:
1. If it can capture now → capture (largest).
2. If any own chain has 1 liberty and can escape (gain ≥ 2 liberties) → escape; else sacrifice least valuable.
3. Else alpha-beta search depth 3–4 with evaluation = (min liberties of own chains) − (min liberties of opponent chains) + small mobility term.
4. Difficulty levels by search depth (1, 2, 4) and random move rate (30%, 15%, 0%).
Unit tests with fixed positions are mandatory.

## Puzzle answer generation
For a critical position: query with `maxVisits=1000`; correct set = best move set (above) AND passes the concept's success check (e.g., `missed_capture` puzzle answer must actually capture or win the capturing race in the PV). Store the PV (≤ 6 moves) as the solution line.
