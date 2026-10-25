"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Board, type Mark } from "@/components/board/Board";
import { Button } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import {
  answerTask,
  getLesson,
  getSchool,
  type AnswerIn,
  type AnswerOut,
  type LessonDetail,
  type LessonTask,
  type Locale,
  type Position,
} from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

type ApiMark = LessonDetail["demo"][number]["marks"][number];
const toMarks = (ms: ApiMark[]): Mark[] => ms.map((m) => ({ point: m.point, kind: m.kind, label: m.label ?? undefined }));

/** One lesson: idea -> demo frames -> tasks (graded by the backend) -> takeaway. */
export function LessonPlayer({ lessonId }: { lessonId: string }) {
  const t = useTranslations("school");
  const locale = useLocale() as Locale;
  const errorText = useErrorText();
  const [lesson, setLesson] = useState<LessonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [screen, setScreen] = useState(0);
  const [nextLesson, setNextLesson] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getLesson(lessonId, locale)
      .then((l) => alive && setLesson(l))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [lessonId, locale, errorText]);

  const header = (
    <header className="flex items-center justify-between gap-3">
      <div>
        {lesson && <p className="text-sm text-ink-soft">{t("lessonN", { n: lesson.order })}</p>}
        <h1 className="text-xl font-semibold">{lesson?.title ?? t("title")}</h1>
      </div>
      <Link href="/school" className="shrink-0 py-1 text-ink-soft underline underline-offset-4">
        {t("backToSchool")}
      </Link>
    </header>
  );

  if (!lesson) {
    return (
      <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
        {header}
        {error && <p role="alert" className="text-bad">{error}</p>}
      </main>
    );
  }

  if (lesson.status === "locked") {
    return (
      <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
        {header}
        <p>{t("locked")}</p>
      </main>
    );
  }

  const frames = lesson.demo;
  const tasks = lesson.tasks;
  const last = 1 + frames.length + tasks.length; // takeaway screen
  const next = () => setScreen((s) => Math.min(last, s + 1));
  const prev = () => setScreen((s) => Math.max(0, s - 1));

  const finish = () => {
    getSchool(locale)
      .then((s) => setNextLesson(s.next_lesson))
      .catch(() => setNextLesson(null));
    next();
  };

  let body: React.ReactNode;
  if (screen === 0) {
    body = (
      <>
        <p className="text-lg leading-relaxed" data-testid="idea">{lesson.idea}</p>
        <div className="flex gap-2">
          <Button variant="primary" onClick={next}>{t("watch")}</Button>
        </div>
      </>
    );
  } else if (screen <= frames.length) {
    const f = frames[screen - 1];
    body = (
      <>
        <BoardView position={f.position} marks={toMarks(f.marks)} />
        <p className="min-h-14 text-lg leading-relaxed" aria-live="polite">{f.text}</p>
        <div className="flex gap-2">
          <Button onClick={prev}>{t("prev")}</Button>
          <Button variant="primary" onClick={next} data-testid="next">{t("next")}</Button>
        </div>
      </>
    );
  } else if (screen < last) {
    const i = screen - 1 - frames.length;
    const task = tasks[i];
    body = (
      <>
        <p className="text-sm text-ink-soft">{t("taskN", { n: i + 1, total: tasks.length })}</p>
        <TaskView key={task.id} lessonId={lesson.id} task={task} onContinue={i === tasks.length - 1 ? finish : next} />
      </>
    );
  } else {
    body = (
      <>
        <p className="text-2xl font-semibold text-ok" data-testid="lesson-done">{t("lessonDone")}</p>
        <div className="rounded-2xl border border-line bg-card p-4">
          <p className="text-sm font-semibold text-ink-soft">{t("takeaway")}</p>
          <p className="text-lg leading-relaxed">{lesson.takeaway}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {nextLesson && (
            <Link href={`/school/${nextLesson}`}>
              <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("nextLesson")}</span>
            </Link>
          )}
          <Link href="/school">
            <span className="inline-flex min-h-11 items-center rounded-full border border-line bg-card px-5 font-semibold">{t("backToSchool")}</span>
          </Link>
        </div>
      </>
    );
  }

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
      {header}
      {body}
    </main>
  );
}

function BoardView({
  position,
  marks,
  onPlay,
  onSelect,
  interactive = false,
}: {
  position: Position;
  marks?: Mark[];
  onPlay?: (p: string) => void;
  onSelect?: (p: string) => void;
  interactive?: boolean;
}) {
  return (
    <div className="rounded-xl shadow-sm">
      <Board
        size={position.board_size}
        stones={position.stones}
        toMove={position.to_move}
        lastMove={position.last_move}
        marks={marks}
        interactive={interactive}
        onPlay={onPlay}
        onSelect={onSelect}
      />
    </div>
  );
}

type Feedback = { correct: boolean; key: string };

function TaskView({ lessonId, task, onContinue }: { lessonId: string; task: LessonTask; onContinue: () => void }) {
  const t = useTranslations("school");
  const errorText = useErrorText();
  const [position, setPosition] = useState<Position>(task.position);
  const [moves, setMoves] = useState<string[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [number, setNumber] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [hintMarks, setHintMarks] = useState<Mark[]>([]);
  const [showHint, setShowHint] = useState(false);
  const [solved, setSolved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async (body: AnswerIn): Promise<AnswerOut | null> => {
    setBusy(true);
    try {
      const res = await answerTask(lessonId, task.id, body);
      setError(null);
      setFeedback({ correct: res.correct, key: res.feedback_key.replace(/^school\.feedback\./, "") });
      setHintMarks(toMarks(res.marks));
      if (res.done) setSolved(true);
      return res;
    } catch (e) {
      setError(errorText(e));
      return null;
    } finally {
      setBusy(false);
    }
  };

  const play = async (point: string) => {
    const res = await send({ moves: [...moves, point] });
    if (res?.correct) {
      setMoves((m) => [...m, point]);
      if (res.position) setPosition(res.position);
    }
  };

  const reset = () => {
    setPosition(task.position);
    setMoves([]);
    setSelected([]);
    setNumber("");
    setFeedback(null);
    setHintMarks([]);
  };

  const toggle = (p: string) => {
    setFeedback(null);
    setSelected((s) => (task.select_mode === "one" ? (s[0] === p ? [] : [p]) : s.includes(p) ? s.filter((x) => x !== p) : [...s, p]));
  };

  const selectMarks: Mark[] = selected.map((p) => ({ point: p, kind: "circle" }));
  const active = !solved && !busy;

  return (
    <div className="flex flex-col gap-3" data-testid={`task-${task.id}`} data-kind={task.kind}>
      <p className="text-lg leading-relaxed">{task.prompt}</p>

      <BoardView
        position={position}
        marks={task.kind === "select" ? [...selectMarks, ...hintMarks] : hintMarks}
        interactive={active && (task.kind === "play" || task.kind === "select")}
        onPlay={task.kind === "play" ? (p) => void play(p) : undefined}
        onSelect={task.kind === "select" ? toggle : undefined}
      />

      <div aria-live="polite" className="min-h-7" data-testid="feedback" data-correct={feedback ? String(feedback.correct) : undefined}>
        {solved ? (
          <p className="font-semibold text-ok">{task.success}</p>
        ) : feedback ? (
          <p className={feedback.correct ? "text-ok" : "text-warn"}>{t(`feedback.${feedback.key}` as "feedback.correct")}</p>
        ) : null}
        {error && <p role="alert" className="text-bad">{error}</p>}
      </div>

      {!solved && task.kind === "count" && (
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            void send({ number: number === "" ? null : Number(number) });
          }}
        >
          <label className="flex items-center gap-2">
            <span>{t("yourAnswer")}</span>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              className="min-h-11 w-24 rounded-lg border border-line bg-card px-3 text-lg"
              data-testid="count-input"
            />
          </label>
          <Button type="submit" variant="primary" disabled={busy}>{t("check")}</Button>
        </form>
      )}

      {!solved && task.kind === "select" && (
        <div className="flex items-center gap-3">
          <Button variant="primary" disabled={busy || selected.length === 0} onClick={() => void send({ points: selected })}>
            {t("check")}
          </Button>
          <span className="text-sm text-ink-soft">{t("selected", { n: selected.length })}</span>
        </div>
      )}

      {!solved && task.kind === "choose" && (
        <div className="flex gap-2">
          <Button onClick={() => void send({ choice: "black" })} disabled={busy}>{t("black")}</Button>
          <Button onClick={() => void send({ choice: "white" })} disabled={busy}>{t("white")}</Button>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!solved && task.kind === "play" && (
          <Button onClick={() => void play("pass")} disabled={busy}>{t("pass")}</Button>
        )}
        {!solved && (
          <Button onClick={() => setShowHint(true)} disabled={showHint}>{t("hint")}</Button>
        )}
        {!solved && (moves.length > 0 || selected.length > 0) && <Button onClick={reset}>{t("reset")}</Button>}
        {solved && (
          <Button variant="primary" onClick={onContinue} data-testid="continue">{t("continue")}</Button>
        )}
      </div>
      {showHint && !solved && <p className="rounded-xl bg-wood/30 p-3">{task.hint}</p>}
    </div>
  );
}
