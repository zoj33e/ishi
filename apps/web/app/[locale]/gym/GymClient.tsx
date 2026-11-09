"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Board, type Mark } from "@/components/board/Board";
import { Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import {
  getGymDue,
  gymAttempt,
  gymHint,
  type GymAttempt,
  type GymContext,
  type GymHint,
  type GymPuzzle,
} from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

const HINT_AREA = 2;
const HINT_ANSWER = 3;
type Frame = GymAttempt["board"];
type Result = { solved: boolean; rating: GymAttempt["rating"]; days: number | null };

/** Shape Gym (09-ui-ux): a stack of short puzzles, one at a time, with the same hint ladder as
 *  lessons. The warm-up is the same screen with today's due cards (`?warmup=1`). */
export function GymClient({ context }: { context: GymContext }) {
  const t = useTranslations("gym");
  const errorText = useErrorText();
  const [puzzles, setPuzzles] = useState<GymPuzzle[] | null>(null);
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<Result[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getGymDue(context)
      .then((r) => alive && setPuzzles(r.puzzles))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [context, errorText]);

  const title = context === "warmup" ? t("warmupTitle") : t("title");
  if (!puzzles) {
    return (
      <Shell title={title}>
        <div className="aspect-square w-full rounded-xl bg-wood/60" />
        <p role={error ? "alert" : "status"} className={error ? "text-bad" : "text-ink-soft"}>
          {error ?? t("loading")}
        </p>
      </Shell>
    );
  }
  if (puzzles.length === 0 || index >= puzzles.length) {
    const solved = results.filter((r) => r.solved).length;
    return (
      <Shell title={title}>
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-5 shadow-soft" data-testid="gym-summary">
          <h2 className="text-lg font-semibold">{puzzles.length === 0 ? t("empty") : t("summaryTitle")}</h2>
          {results.length > 0 && <p>{t("summary", { solved, total: results.length })}</p>}
          <Link href="/" className="self-start">
            <span className="inline-flex min-h-11 items-center rounded-control bg-ink px-5 font-semibold text-paper transition-colors duration-150 hover:bg-ink-raised">{t("home")}</span>
          </Link>
        </section>
      </Shell>
    );
  }
  return (
    <Shell title={title}>
      <p className="text-sm text-ink-soft" data-testid="gym-progress">
        {t("progress", { n: index + 1, total: puzzles.length })}
      </p>
      <PuzzleCard
        key={puzzles[index].id}
        puzzle={puzzles[index]}
        context={context}
        last={index + 1 === puzzles.length}
        onNext={(r) => {
          setResults((rs) => [...rs, r]);
          setIndex((i) => i + 1);
        }}
      />
    </Shell>
  );
}

function PuzzleCard({
  puzzle,
  context,
  last,
  onNext,
}: {
  puzzle: GymPuzzle;
  context: GymContext;
  last: boolean;
  onNext: (r: Result) => void;
}) {
  const t = useTranslations("gym");
  const errorText = useErrorText();
  const started = useRef(0);
  useEffect(() => {
    started.current = Date.now();
  }, []);
  const [moves, setMoves] = useState<string[]>([]);
  const [board, setBoard] = useState<Frame>({ stones: puzzle.position.stones, last_move: null });
  const [wrong, setWrong] = useState(0);
  const [hint, setHint] = useState<GymHint | null>(null);
  const [feedback, setFeedback] = useState<{ text: string; good: boolean } | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [frame, setFrame] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const level = hint?.level ?? 0;
  const elapsed = () => Date.now() - started.current;
  const color = puzzle.to_move === "black" ? t("black") : t("white");

  const play = async (point: string) => {
    setBusy(true);
    setError(null);
    try {
      const seq = [...moves, point];
      const r = await gymAttempt(puzzle.id, {
        moves: seq,
        hints_used: level,
        time_ms: elapsed(),
        wrong_tries: wrong,
        context,
      });
      setBoard(r.board);
      if (r.done) {
        finish(r.solved, r.rating, r.next_due_at ?? null, r.solution_frames ?? []);
        setFeedback(r.solved ? { text: t("correct"), good: true } : { text: t("failed"), good: false });
      } else if (r.correct) {
        setMoves(r.opponent_reply ? [...seq, r.opponent_reply] : seq);
        setFeedback({ text: t("keepGoing"), good: true });
      } else {
        setWrong((w) => w + 1);
        setFeedback({ text: t("tryAgain"), good: false });
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const askHint = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = Math.min(level + 1, HINT_ANSWER);
      const h = await gymHint(puzzle.id, { level: next, hints_used: next, time_ms: elapsed(), wrong_tries: wrong, context });
      setHint(h);
      if (h.level >= HINT_ANSWER) {
        finish(false, h.rating, h.next_due_at ?? null, h.solution_frames ?? []);
        setFeedback({ text: t("answerShown"), good: false });
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const finish = (solved: boolean, rating: Result["rating"], nextDue: string | null, f: Frame[]) => {
    const days = nextDue ? Math.max(1, Math.round((Date.parse(nextDue) - Date.now()) / 86_400_000)) : null;
    setResult({ solved, rating, days });
    setFrames(f);
    setFrame(0);
  };

  const shown = result && frame > 0 ? frames[frame - 1] : board;
  const marks: Mark[] = !result && level >= 1 ? (hint?.marks ?? []).map((p) => ({ point: p, kind: "triangle" })) : [];
  const days = result?.days ?? null;

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-ink px-2 py-1 text-sm font-semibold text-paper" data-testid="concept-tag">
          {t(`concept.${puzzle.concept_id}` as "concept.missed_capture")}
        </span>
        {puzzle.source === "own_mistake" && (
          <span className="rounded-md border border-line px-2 py-1 text-sm">{t("fromYourGame")}</span>
        )}
      </div>
      <div className="rounded-xl shadow-sm">
        <Board
          size={puzzle.position.board_size}
          stones={shown.stones}
          toMove={puzzle.to_move}
          lastMove={shown.last_move}
          marks={marks}
          highlight={!result && level >= HINT_AREA ? hint?.focus : null}
          interactive={!result && !busy}
          onPlay={(p) => void play(p)}
        />
      </div>
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-5 shadow-soft" aria-live="polite" data-testid="gym-panel">
        <h2 className="text-lg font-semibold" data-testid="to-play">
          {t("toPlay", { color })}
        </h2>
        {!result && (
          <p className="text-ink-soft">
            {puzzle.learner_moves > 1 ? t(`task.${puzzle.concept_id}` as "task.missed_capture") + " " + t("chase") : t(`task.${puzzle.concept_id}` as "task.missed_capture")}
          </p>
        )}
        {!result && level >= 1 && (
          <p className="rounded-xl bg-paper px-3 py-2" data-testid="hint">
            {level >= HINT_AREA ? t("hintArea") : t(`hint.${puzzle.concept_id}` as "hint.missed_capture")}
          </p>
        )}
        {feedback && (
          <p className={`font-semibold ${feedback.good ? "text-ok" : "text-warn"}`} data-testid="feedback">
            {feedback.text}
          </p>
        )}
        {!result && (
          <Button className="self-start" onClick={() => void askHint()} disabled={busy}>
            {level >= HINT_AREA ? t("showAnswer") : t("hintButton")}
          </Button>
        )}
        {result && (
          <>
            {days !== null && <p className="text-sm text-ink-soft" data-testid="next-due">{t("nextDue", { days })}</p>}
            {frames.length > 0 && (
              <div className="flex flex-col gap-2" data-testid="replay">
                <p className="text-sm text-ink-soft">
                  {t("replayTitle")} · {t("step", { n: frame, total: frames.length })}
                </p>
                <div className="flex gap-2">
                  <Button onClick={() => setFrame((f) => Math.max(0, f - 1))} disabled={frame === 0}>{t("back")}</Button>
                  <Button onClick={() => setFrame((f) => Math.min(frames.length, f + 1))} disabled={frame >= frames.length}>
                    {t("forward")}
                  </Button>
                </div>
              </div>
            )}
            <Button variant="primary" onClick={() => onNext(result)} data-testid="gym-next">
              {last ? t("finish") : t("next")}
            </Button>
          </>
        )}
      </section>
      <p role="alert" className="min-h-6 text-bad">{error}</p>
    </>
  );
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const t = useTranslations("gym");
  return (
    <main className="mx-auto flex max-w-md flex-col gap-3 px-4 py-6">
      <header className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">{title}</h1>
        <Link href="/" className="shrink-0 py-1 text-ink-soft underline underline-offset-4">{t("home")}</Link>
      </header>
      {children}
    </main>
  );
}
