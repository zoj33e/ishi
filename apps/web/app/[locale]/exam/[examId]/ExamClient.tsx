"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Board } from "@/components/board/Board";
import { Button, ButtonLink, Card } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { createGame, examAttempt, getExam, type Exam, type ExamAttempt, type ExamPuzzle } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

type Frame = ExamAttempt["board"];

/** Belt exams. White -> Yellow (D-023): win 3 capture games before losing 3. Orange -> Brown
 *  (M8): a rules screen, 12 puzzles (one try, no hints, 10 needed), then best of 3 9x9 games
 *  against the belt's bot with no teacher questions, then the result. */
export function ExamClient({ examId }: { examId: string }) {
  const t = useTranslations("exam");
  const tb = useTranslations("belts");
  const router = useRouter();
  const errorText = useErrorText();
  const [exam, setExam] = useState<Exam | null>(null);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    getExam(examId)
      .then((e) => alive && setExam(e))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [examId, errorText]);

  const yellow = exam?.belt_target === "yellow";
  const placement = exam?.belt_target === "placement";
  const belt = exam && !placement ? tb(exam.belt_target as "yellow") : "";

  const play = async () => {
    if (!exam) return;
    setBusy(true);
    try {
      const id =
        exam.active_game ??
        (await createGame(yellow ? { mode: "capture", exam_id: exam.id } : { mode: "full", exam_id: exam.id })).id;
      router.push(`/play/${id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const answered = exam?.puzzles.filter((p) => p.solved !== null).length ?? 0;
  const fresh = exam !== null && !yellow && exam.phase === "puzzles" && answered === 0 && !started;
  const current = exam?.puzzles.find((p) => p.solved === null) ?? null;

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{!exam ? " " : placement ? t("placementTitle") : t("title", { belt })}</h1>
        <Link href="/" className="py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>

      {exam && yellow && (
        <Card>
          <p className="leading-relaxed">{t("rulesYellow")}</p>
          <p className="text-lg font-semibold" data-testid="exam-score">
            {t("score", { won: exam.games_won, lost: exam.games_lost, wins: exam.wins_needed, losses: exam.losses_allowed })}
          </p>
          {exam.status === "in_progress" && (
            <Button variant="primary" className="self-start" disabled={busy} onClick={() => void play()}>
              {exam.active_game ? t("resume") : t("play")}
            </Button>
          )}
        </Card>
      )}

      {exam && fresh && (
        <Card title={placement ? t("placementRulesTitle") : t("rulesTitle")}>
          {placement && <p className="text-ink-soft">{t("placementIntro")}</p>}
          <ol className="flex list-decimal flex-col gap-2 pl-5" data-testid="exam-rules">
            <li>{t(placement ? "placementPuzzles" : "rulesPuzzles", { total: exam.puzzles.length, needed: exam.puzzles_needed })}</li>
            <li>{t(placement ? "placementGame" : "rulesGames", { bot: exam.bot_label ?? "" })}</li>
            <li>{placement ? t("placementNoHelp") : t("rulesNoHelp")}</li>
          </ol>
          <Button variant="primary" className="self-start" onClick={() => setStarted(true)} data-testid="exam-begin">
            {t("begin")}
          </Button>
        </Card>
      )}

      {exam && !yellow && exam.phase === "puzzles" && !fresh && current && (
        <>
          <p className="text-sm text-ink-soft" data-testid="exam-progress">
            {t("puzzleProgress", { n: answered + 1, total: exam.puzzles.length, solved: exam.puzzle_score })}
          </p>
          <ExamPuzzleCard key={current.puzzle.id} examId={exam.id} item={current} onDone={setExam} />
        </>
      )}

      {exam && !yellow && exam.phase !== "puzzles" && (
        <Card>
          <p data-testid="exam-puzzle-score">{t("puzzleScore", { solved: exam.puzzle_score, total: exam.puzzles.length })}</p>
          {exam.phase === "games" && (
            <>
              {placement ? (
                <p className="leading-relaxed">{t("placementGameNow", { bot: exam.bot_label ?? "" })}</p>
              ) : (
                <>
                  <p className="leading-relaxed">{t("rulesGames", { bot: exam.bot_label ?? "" })}</p>
                  <p className="text-lg font-semibold" data-testid="exam-score">
                    {t("score", { won: exam.games_won, lost: exam.games_lost, wins: exam.wins_needed, losses: exam.losses_allowed })}
                  </p>
                </>
              )}
              <Button variant="primary" className="self-start" disabled={busy} onClick={() => void play()} data-testid="exam-play">
                {exam.active_game ? t("resume") : placement ? t("placementPlay") : t("play")}
              </Button>
            </>
          )}
        </Card>
      )}

      {placement && exam?.placed_belt && <PlacementResult belt={exam.placed_belt} />}

      {!placement && exam?.status === "passed" && (
        <section className="belt-award flex flex-col items-center gap-3 rounded-2xl border border-line bg-card p-6 text-center shadow-soft" data-testid="exam-passed">
          <span className={`belt-ribbon belt-${exam.belt_target}`} aria-hidden />
          <p className="text-2xl font-semibold text-ok">{t("passed", { belt })}</p>
          <Link href="/progress">
            <span className="inline-flex min-h-11 items-center rounded-control bg-ink px-5 font-semibold text-paper transition-colors duration-150 hover:bg-ink-raised">{t("seeProgress")}</span>
          </Link>
        </section>
      )}
      {!placement && exam?.status === "failed" && (
        <Card>
          <p className="text-warn" data-testid="exam-failed">
            {yellow ? t("failedYellow") : exam.puzzle_score < exam.puzzles_needed && exam.games_won + exam.games_lost === 0 ? t("failedPuzzles") : t("failed")}
          </p>
        </Card>
      )}

      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>
    </main>
  );
}

/** Where the placement test put the learner (D-068): White goes to lesson 1, Yellow or Orange
 *  go to today's plan with the rules school marked done. */
function PlacementResult({ belt }: { belt: string }) {
  const t = useTranslations("exam");
  const tb = useTranslations("belts");
  const white = belt === "white";
  return (
    <section className="belt-award flex flex-col items-center gap-3 rounded-2xl border border-line bg-card p-6 text-center shadow-soft" data-testid="placement-result" data-belt={belt}>
      <span className={`belt-ribbon belt-${belt}`} aria-hidden />
      <p className="font-serif text-2xl font-semibold">{tb(belt as "white")}</p>
      {!white && <p className="text-lg font-semibold text-ok">{belt === "orange" ? t("placedOrange") : t("placedYellow")}</p>}
      <p className="text-ink-soft">{white ? t("placedWhite") : t("placedPast")}</p>
      <ButtonLink href={white ? "/school" : "/"} variant="primary" size="lg" className="self-stretch" data-testid="placement-next">
        {white ? t("toSchool") : t("toHome")}
      </ButtonLink>
    </section>
  );
}

/** One exam puzzle: one try, no hints. A wrong move answers it; then the answer is shown. */
function ExamPuzzleCard({ examId, item, onDone }: { examId: string; item: ExamPuzzle; onDone: (e: Exam) => void }) {
  const t = useTranslations("exam");
  const tg = useTranslations("gym");
  const errorText = useErrorText();
  const puzzle = item.puzzle;
  const started = useRef(0);
  useEffect(() => {
    started.current = Date.now();
  }, []);
  const [moves, setMoves] = useState<string[]>([]);
  const [board, setBoard] = useState<Frame>({ stones: puzzle.position.stones, last_move: null });
  const [result, setResult] = useState<{ solved: boolean; exam: Exam; frames: Frame[] } | null>(null);
  const [frame, setFrame] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const play = async (point: string) => {
    setBusy(true);
    setError(null);
    try {
      const seq = [...moves, point];
      const r = await examAttempt(examId, puzzle.id, { moves: seq, time_ms: Date.now() - started.current });
      setBoard(r.board);
      if (r.done) {
        setResult({ solved: r.correct, exam: r.exam, frames: r.solution_frames ?? [] });
        setFrame(0);
      } else {
        setMoves(r.opponent_reply ? [...seq, r.opponent_reply] : seq);
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const shown = result && frame > 0 ? result.frames[frame - 1] : board;
  const color = puzzle.to_move === "black" ? tg("black") : tg("white");
  const task = tg(`task.${puzzle.concept_id}` as "task.missed_capture");

  return (
    <>
      <span className="self-start rounded-md bg-ink px-2 py-1 text-sm font-semibold text-paper" data-testid="concept-tag">
        {tg(`concept.${puzzle.concept_id}` as "concept.missed_capture")}
      </span>
      <div className="rounded-xl shadow-sm">
        <Board
          size={puzzle.position.board_size}
          stones={shown.stones}
          toMove={puzzle.to_move}
          lastMove={shown.last_move}
          interactive={!result && !busy}
          onPlay={(p) => void play(p)}
        />
      </div>
      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-5 shadow-soft" aria-live="polite" data-testid="exam-panel">
        <h2 className="text-lg font-semibold">{tg("toPlay", { color })}</h2>
        {!result && <p className="text-ink-soft">{puzzle.learner_moves > 1 ? `${task} ${tg("chase")}` : task}</p>}
        {!result && moves.length > 0 && <p className="font-semibold text-ok">{tg("keepGoing")}</p>}
        {result && (
          <>
            <p className={`font-semibold ${result.solved ? "text-ok" : "text-warn"}`} data-testid="exam-feedback">
              {result.solved ? t("puzzleSolved") : t("puzzleMissed")}
            </p>
            {result.frames.length > 0 && (
              <div className="flex flex-col gap-2">
                <p className="text-sm text-ink-soft">
                  {tg("replayTitle")} · {tg("step", { n: frame, total: result.frames.length })}
                </p>
                <div className="flex gap-2">
                  <Button onClick={() => setFrame((f) => Math.max(0, f - 1))} disabled={frame === 0}>{tg("back")}</Button>
                  <Button onClick={() => setFrame((f) => Math.min(result.frames.length, f + 1))} disabled={frame >= result.frames.length}>
                    {tg("forward")}
                  </Button>
                </div>
              </div>
            )}
            <Button variant="primary" onClick={() => onDone(result.exam)} data-testid="exam-next">
              {tg("next")}
            </Button>
          </>
        )}
      </section>
      <p role="alert" className="min-h-6 text-bad">{error}</p>
    </>
  );
}
