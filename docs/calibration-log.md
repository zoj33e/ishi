# Bot calibration log

Appended by `scripts/calibrate_bots.py`. Target: the stronger bot of each adjacent pair wins about 60%.

## 2026-10-25 16:21 UTC — 50 games per pair, seed 1

Weak blunder rates: {22: 0.06, 24: 0.15, 26: 0.28, 28: 0.45, 30: 0.7}. Bot visits 40. All bot moves: p50 258 ms, p95 323 ms. Run time 13.8 min.

| Match (weak vs strong) | weak blunder | strong wins | draws | resigned | avg moves | p95 ms |
|---|---|---|---|---|---|---|
| 30k vs 28k | 0.70 | 29/50 (58%) | 0 | 50 | 32 | 314 |
| 28k vs 26k | 0.45 | 33/50 (66%) | 0 | 50 | 32 | 335 |
| 26k vs 24k | 0.28 | 30/50 (60%) | 1 | 49 | 33 | 315 |
| 24k vs 22k | 0.15 | 26/50 (52%) | 0 | 50 | 31 | 312 |
| 22k vs 20k | 0.06 | 42/50 (84%) | 1 | 46 | 30 | 325 |
| 20k vs 15k | 0.00 | 33/50 (66%) | 2 | 48 | 31 | 338 |
| 15k vs 10k | 0.00 | 32/50 (64%) | 3 | 43 | 33 | 340 |
| 10k vs 5k | 0.00 | 32/50 (64%) | 1 | 49 | 30 | 295 |
| 5k vs 1d | 0.00 | 42/50 (84%) | 3 | 45 | 31 | 319 |

## 2026-10-25 16:45 UTC — 50 games per pair, seed 1

Weak blunder rates: {22: 0.06, 24: 0.15, 26: 0.28, 28: 0.45, 30: 0.7}, temperatures: {22: 1.0, 24: 1.15, 26: 1.3, 28: 1.3, 30: 1.3}. Bot visits 40. All bot moves: p50 282 ms, p95 341 ms. Run time 5.1 min.

| Match (weak vs strong) | weak blunder | strong wins | draws | resigned | avg moves | p95 ms |
|---|---|---|---|---|---|---|
| 26k vs 24k | 0.28 | 34/50 (68%) | 0 | 50 | 31 | 331 |
| 24k vs 22k | 0.15 | 34/50 (68%) | 1 | 49 | 30 | 344 |
| 22k vs 20k | 0.06 | 34/50 (68%) | 1 | 48 | 30 | 344 |
