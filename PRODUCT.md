# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
The builder: a total Go beginner, Thai speaker, comfortable in English, studying about 20 minutes a day on phone and PC (docs/01-product-prd.md). Secondary, post-MVP: Thai and South-East Asian beginners and school Go clubs.

The first-time user does not know what Go is, what a liberty is, or what a belt means; every first screen must make sense to someone who has never seen a Go board.

## Product Purpose
Ishi takes a total beginner to single-digit kyu fast. KataGo provides the truth, a deterministic Why Engine turns it into teachable facts, and Claude narrates those facts like a patient human teacher, in Thai or English. Success is the learner's estimated rank rising over time (hypothesis: 15k in 60 days, 10k in 120 days at ~20 min/day).

## Positioning
A teacher, not a playing site: one lesson per game, chosen for the learner's level, explained in plain language and drilled until it sticks. The LLM never judges the board; every explanation comes from engine facts.

## Operating Context
- Daily session (~20 min): warm-up puzzles → one 9x9 game vs a humanlike bot at the learner's level → exactly one lesson from that game.
- First launch path: rules school (10 lessons) → Capture Go → Yellow belt exam → first 9x9 game.
- Runs locally: backend on the home PC, the web app installed as a PWA on phone or PC.

## Capabilities and Constraints
- Screens: home, rules school, lesson player, Capture Go, 9x9 game with in-game nudges, post-game lesson, Shape Gym (spaced repetition), belt exams, progress (rank chart, belt path).
- Belts: White → Yellow → Orange → Green → Blue → Purple → Brown (exams from Orange up).
- Bilingual from day one: every user-facing string goes through next-intl messages (`th`, `en`); Thai is the default locale.
- Mobile-first; must work at 375x812 with no horizontal scroll; touch, mouse and keyboard play on the board.
- Single user, local, no accounts.

## Brand Commitments
- Name "Ishi" (stone) — placeholder, may be renamed (docs/13-decisions.md Q5).
- Voice: a patient, calm teacher. Never shames mistakes; asks questions before telling.

## Evidence on Hand
No testimonials, users, or measured outcomes yet. Do not invent any.

## Product Principles
1. One clear next step: the learner should never wonder what to do now.
2. One lesson at a time: never dump a list of mistakes.
3. Teach at the learner's level: only show what they are ready for.
4. Calm over gamified noise: progress is shown, not shouted.

## Accessibility & Inclusion
Thai and English must both read well (Thai needs generous line height). Large touch targets (≥44 px), keyboard play on the board, reduced-motion respected.
