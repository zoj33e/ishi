"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Board } from "@/components/board/Board";
import { TeacherMark } from "@/components/TeacherMark";
import { Button } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import {
  finishLesson,
  getGameLesson,
  lessonHint,
  retryLesson,
  type GameLesson,
  type Locale,
  type LessonStatus,
} from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

const POLL_MS = 1500;
const HINT_AREA = 2;
const HINT_SOLUTION = 3;

type Stage = "explain" | "try" | "replay" | "takeaway";

/** The post-game lesson (09-ui-ux screen 5): the critical moment, the teacher's explanation one
 *  sentence at a time, a retry with the hint ladder, the solution replay, then the takeaway. */
export function LessonClient({ gameId }: { gameId: string }) {
  const t = useTranslations("lesson");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const errorText = useErrorText();
  const [lesson, setLesson] = useState<GameLesson | null>(null);
  const [status, setStatus] = useState<LessonStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [shown, setShown] = useState(1); // explanation sentences revealed
  const [stage, setStage] = useState<Stage>("explain");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [frame, setFrame] = useState(0); // replay step, 0 = the lesson position
  const [busy, setBusy] = useState(false);
  const [puzzleAdded, setPuzzleAdded] = useState<boolean | null>(null);

  // Load the lesson; while the teacher prepares it, ask again every 1.5 s.
  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () =>
      getGameLesson(gameId, locale)
        .then((r) => {
          if (!alive) return;
          if ("lesson" in r) {
            setLesson(r.lesson);
            setStatus(null);
            if (r.lesson.retry_result) setStage(r.lesson.done ? "takeaway" : "replay");
          } else {
            setStatus(r.status);
            if (r.status === "preparing") timer = setTimeout(load, POLL_MS);
          }
        })
        .catch((e: unknown) => alive && setError(errorText(e)));
    void load();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [gameId, locale, errorText]);

  if (!lesson) {
    return (
      <Shell title={t("title")}>
        <div className="aspect-square w-full rounded-xl bg-wood/60" />
        <p className="text-ink-soft" aria-live="polite" data-testid="lesson-status">
          {status === "unavailable" ? t("unavailable") : status === "preparing" ? t("preparing") : " "}
        </p>
        <p role="alert" className="min-h-6 text-bad">{error}</p>
      </Shell>
    );
  }

  const n = lesson.narration;
  const hints = n.hints ?? [];
  const marks = (n.marks ?? []).map((m) => ({ ...m, label: m.label ?? undefined }));
  const mistake = lesson.lesson_type === "mistake";
  const allShown = shown >= n.explanation.length;
  const frames = lesson.solution_frames;
  const onFrame = stage === "replay" && frame > 0 ? frames[frame - 1] : null;
  const stones = onFrame?.stones ?? lesson.position.stones;
  const faded =
    lesson.played_move && !onFrame && stage !== "replay"
      ? [{ point: lesson.played_move, color: lesson.learner_color }]
      : [];
  const tag = mistake
    ? lesson.severity && t(`severity.${lesson.severity}`)
    : lesson.lesson_type === "praise"
      ? t("praiseTag")
      : t("cleanTag");
  const tagColor =
    lesson.severity === "big" ? "bg-bad" : lesson.severity === "medium" ? "bg-warn" : mistake ? "bg-warn/60" : "bg-ok";

  const apply = (l: GameLesson) => {
    setLesson(l);
    if (l.retry_result) {
      setStage("replay");
      setFrame(0);
    }
  };

  const retry = async (point: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await retryLesson(lesson.lesson_id, point);
      setFeedback(t(r.feedback_key.replace(/^lesson\./, "") as "retry.correct"));
      apply(r.lesson);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const hint = async () => {
    setBusy(true);
    try {
      const l = await lessonHint(lesson.lesson_id);
      if (l.hint_level >= HINT_SOLUTION) setFeedback(t("retry.solution"));
      apply(l);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const toTakeaway = async () => {
    setStage("takeaway");
    setBusy(true);
    try {
      setPuzzleAdded((await finishLesson(lesson.lesson_id)).puzzle_added);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const hintText =
    lesson.hint_level >= 1 && lesson.hint_level < HINT_SOLUTION ? hints[Math.min(lesson.hint_level, hints.length) - 1] : null;

  return (
    <Shell title={lesson.move_number ? `${t("title")} · ${t("moveLabel", { n: lesson.move_number })}` : t("title")}>
      <div className="rounded-xl shadow-sm">
        <Board
          size={lesson.position.board_size}
          stones={stones}
          toMove={lesson.learner_color}
          lastMove={onFrame ? onFrame.last_move : lesson.position.last_move}
          marks={stage === "explain" || stage === "try" ? marks : []}
          faded={faded}
          highlight={stage === "try" && lesson.hint_level >= HINT_AREA ? lesson.focus : null}
          interactive={stage === "try" && lesson.can_retry && !busy}
          onPlay={(p) => void retry(p)}
        />
      </div>
      {faded.length > 0 && stage === "explain" && mistake && <p className="text-sm text-ink-soft">{t("faded")}</p>}

      <section className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-4 shadow-md" aria-live="polite" data-testid="teacher-panel">
        <div className="flex items-center gap-3">
          <TeacherMark className="h-10 w-10 shrink-0" />
          {tag && <span className={`rounded-full px-3 py-1 text-sm font-semibold text-paper ${tagColor}`} data-testid="lesson-tag">{tag}</span>}
        </div>
        <h2 className="text-lg font-semibold" data-testid="headline">{n.headline}</h2>

        {stage === "explain" && (
          <>
            <ul className="flex flex-col gap-2">
              {n.explanation.slice(0, shown).map((s, i) => (
                <li key={i} data-testid="explanation">{s}</li>
              ))}
            </ul>
            {!allShown && <Button variant="primary" onClick={() => setShown((k) => k + 1)}>{t("next")}</Button>}
            {allShown && mistake && lesson.can_retry && (
              <>
                {n.question && <p className="font-semibold" data-testid="question">{n.question}</p>}
                <Button variant="primary" onClick={() => setStage("try")}>{t("tryIt")}</Button>
              </>
            )}
            {allShown && (!mistake || !lesson.can_retry) && (
              <Button variant="primary" onClick={() => (mistake ? setStage("replay") : void toTakeaway())}>{t("next")}</Button>
            )}
          </>
        )}

        {stage === "try" && (
          <>
            {n.question && <p className="font-semibold" data-testid="question">{n.question}</p>}
            <p className="text-ink-soft">{t("playPrompt")}</p>
            {hintText && <p className="rounded-xl bg-paper px-3 py-2" data-testid="hint">{hintText}</p>}
            {feedback && <p className="font-semibold text-warn" data-testid="feedback">{feedback}</p>}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void hint()} disabled={busy}>
                {lesson.hint_level >= HINT_AREA ? t("showMove") : t("hint")}
              </Button>
            </div>
          </>
        )}

        {stage === "replay" && (
          <>
            {feedback && (
              <p className={`font-semibold ${lesson.retry_result === "failed" ? "text-warn" : "text-ok"}`} data-testid="feedback">
                {feedback}
              </p>
            )}
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
            <Button variant="primary" onClick={() => void toTakeaway()}>{t("next")}</Button>
          </>
        )}

        {stage === "takeaway" && (
          <>
            <p className="text-sm font-semibold uppercase tracking-wide text-ink-soft">{t("takeaway")}</p>
            <p data-testid="takeaway">{n.takeaway}</p>
            {puzzleAdded && <span className="self-start rounded-full bg-ok px-3 py-1 text-sm font-semibold text-paper" data-testid="gym-chip">{t("addedToGym")}</span>}
            <Button variant="primary" disabled={busy} onClick={() => router.push("/")}>{busy ? t("finishing") : t("done")}</Button>
          </>
        )}
      </section>

      <p role="alert" className="min-h-6 text-bad">{error}</p>
    </Shell>
  );
}

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  const t = useTranslations("lesson");
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
