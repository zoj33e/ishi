"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";
import { Diagram, type DiagramStone } from "@/components/Diagram";
import { Button, ButtonLink } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import {
  createGame,
  getBotRanks,
  getMe,
  getSchool,
  getToday,
  startExam,
  startPlacement,
  type BotRanks,
  type Locale,
  type Me,
  type School,
  type Today,
} from "@/lib/api";
import { rankLabel } from "@/lib/rank";
import { useErrorText } from "@/lib/useErrorText";

type Data = { me: Me; today: Today; school: School; ranks: BotRanks };

/** The one thing to do now (PRODUCT.md principle 1). */
type Next = {
  key: string;
  title: string;
  meta?: string;
  body: string;
  cta: string;
  href?: string;
  run?: () => void;
  art: "lesson" | "capture" | "game" | "exam" | "warmup";
};

const ART: Record<Exclude<Next["art"], "exam">, { stones: DiagramStone[]; view?: [number, number, number, number]; size?: number }> = {
  lesson: {
    stones: [
      { at: [1, 2], color: "b" },
      { at: [2, 1], color: "b" },
      { at: [3, 2], color: "b" },
      { at: [2, 2], color: "w", mark: "triangle" },
    ],
    view: [0, 0, 4, 4],
  },
  capture: {
    size: 7,
    stones: [
      { at: [2, 2], color: "b" },
      { at: [3, 2], color: "w" },
      { at: [3, 3], color: "b" },
      { at: [4, 2], color: "b" },
      { at: [3, 1], color: "b", mark: "triangle" },
    ],
  },
  game: {
    stones: [
      { at: [2, 2], color: "b" },
      { at: [6, 6], color: "w" },
      { at: [6, 2], color: "b" },
      { at: [2, 6], color: "w" },
      { at: [4, 4], color: "b" },
    ],
  },
  warmup: {
    stones: [
      { at: [1, 1], color: "w" },
      { at: [2, 1], color: "b" },
      { at: [1, 2], color: "b" },
      { at: [2, 2], color: "w", mark: "triangle" },
    ],
    view: [0, 0, 3, 3],
  },
};

const CAPTURE_GAMES_FOR_EXAM = 5;

export function HomeClient() {
  const t = useTranslations("home");
  const tb = useTranslations("belts");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const errorText = useErrorText();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [botRank, setBotRank] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([getMe(), getToday(), getSchool(locale), getBotRanks()])
      .then(([me, today, school, ranks]) => {
        if (!alive) return;
        const fresh = me.belt === "white" && !school.lessons.some((l) => l.status === "done");
        if (fresh && me.settings?.welcomed !== true) {
          router.replace("/welcome"); // first launch: what Go is, then lesson 1
          return;
        }
        setData({ me, today, school, ranks });
      })
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [locale, errorText, router]);

  const go = async (action: () => Promise<string>) => {
    setBusy(true);
    try {
      router.push(await action());
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const playCapture = () => go(async () => `/play/${(await createGame({ mode: "capture" })).id}`);
  const playFull = (rank: number) =>
    go(async () => `/play/${(await createGame({ mode: "full", bot_rank: rank })).id}`);
  const takeExam = () => go(async () => `/exam/${(await startExam()).id}`);
  const takePlacement = () => go(async () => `/exam/${(await startPlacement()).id}`);

  if (!data) {
    return (
      <p role={error ? "alert" : "status"} className={`py-16 text-center ${error ? "text-bad" : "text-ink-soft"}`}>
        {error ?? t("starting")}
      </p>
    );
  }

  const { me, today, school, ranks } = data;
  const rank = botRank ?? ranks.recommended;
  const rankOptions = [...new Set([...ranks.ranks, ranks.recommended])].sort((a, b) => b - a);
  const full = today.game.mode === "full";
  const examBelt = today.exam_belt ? tb(today.exam_belt as "yellow") : "";
  const total = school.lessons.length;
  const done = school.lessons.filter((l) => l.status === "done").length;
  const nextIndex = school.lessons.findIndex((l) => l.id === school.next_lesson);
  const nextLesson = nextIndex >= 0 ? school.lessons[nextIndex] : undefined;
  const cap = today.capture;

  let next: Next;
  if (today.exam_in_progress) {
    const placing = today.exam_in_progress_target === "placement";
    next = {
      key: "exam-continue",
      title: placing ? t("placementTitle") : t("examTitle", { belt: examBelt }),
      body: placing ? t("nextPlacementBody") : t("nextExamBody"),
      cta: t("examContinue"),
      href: `/exam/${today.exam_in_progress}`,
      art: "exam",
    };
  } else if (today.lesson_game) {
    next = { key: "lesson", title: t("todayLessonReady"), body: t("lessonReady"), cta: t("lessonOpen"), href: `/lesson/${today.lesson_game}`, art: "lesson" };
  } else if (nextLesson && me.belt === "white") {
    // after White belt the rules school is review, found under "Practise anytime"
    next = {
      key: "school",
      title: nextLesson.title,
      meta: t("nextSchoolMeta", { n: nextIndex + 1, total }),
      body: t("nextSchoolBody"),
      cta: done === 0 ? t("nextSchoolStart") : t("nextSchoolContinue"),
      href: `/school/${nextLesson.id}`,
      art: "lesson",
    };
  } else if (today.exam_available) {
    next = {
      key: "exam",
      title: t("examTitle", { belt: examBelt }),
      body: me.belt === "white" ? t("examReady") : t("examReadyBelt"),
      cta: t("examStart"),
      run: () => void takeExam(),
      art: "exam",
    };
  } else if (!full) {
    next = {
      key: "capture",
      title: t("captureTitle"),
      meta: t("nextCaptureMeta", { stage: cap.stage, total: cap.stages_total }),
      body: t("nextCaptureBody", { size: cap.board_size, target: cap.capture_target }),
      cta: t("capturePlay"),
      run: () => void playCapture(),
      art: "capture",
    };
  } else if (today.warmup_due > 0) {
    next = { key: "warmup", title: t("todayWarmup", { n: today.warmup_due }), body: t("nextWarmupBody"), cta: t("gymWarmup"), href: "/gym?warmup=1", art: "warmup" };
  } else {
    next = {
      key: "game",
      title: t("todayGame", { bot: rankLabel(ranks.recommended) }),
      body: t("nextGameBody"),
      cta: t("fullPlay"),
      run: () => void playFull(ranks.recommended),
      art: "game",
    };
  }

  // the day's loop, shown under the next step once real games start
  const dayStep = next.key === "warmup" ? 0 : next.key === "game" ? 1 : next.key === "lesson" ? 2 : -1;

  const pastRules = !nextLesson || me.belt !== "white"; // rules learned, or past White belt anyway
  const practice: ReactNode[] = [];
  if (next.key !== "school") {
    practice.push(
      <PracticeRow key="school" title={t("schoolTitle")} detail={done < total ? t("schoolProgress", { done, total }) : t("schoolDone")}>
        <ButtonLink href="/school">{t("open")}</ButtonLink>
      </PracticeRow>,
    );
  }
  if (next.key !== "capture" && (pastRules || cap.games_played > 0)) {
    practice.push(
      <PracticeRow
        key="capture"
        title={t("captureTitle")}
        detail={t("captureInfo", { stage: cap.stage, total: cap.stages_total, size: cap.board_size, target: cap.capture_target })}
      >
        <Button disabled={busy} onClick={() => void playCapture()}>
          {t("play")}
        </Button>
      </PracticeRow>,
    );
  }
  if (pastRules && next.key !== "warmup") {
    practice.push(
      <PracticeRow key="gym" title={t("gymTitle")} detail={t("gymDue", { n: today.warmup_due })}>
        <ButtonLink href={today.warmup_due > 0 ? "/gym?warmup=1" : "/gym"}>{t("open")}</ButtonLink>
      </PracticeRow>,
    );
  }
  if (ranks.unlocked) {
    practice.push(
      <PracticeRow key="full" title={t("fullTitle")} detail={t("fullInfo")}>
        <div className="flex w-full flex-wrap items-center gap-2">
          <label className="flex flex-1 items-center gap-2 text-sm">
            <span className="sr-only">{t("fullStrength")}</span>
            <select
              className="min-h-11 w-full rounded-control border border-line bg-card px-4"
              value={rank}
              onChange={(e) => setBotRank(Number(e.target.value))}
              data-testid="bot-rank"
              aria-label={t("fullStrength")}
            >
              {rankOptions.map((r) => (
                <option key={r} value={r}>
                  {r === ranks.recommended ? t("fullRecommended", { rank: rankLabel(r) }) : rankLabel(r)}
                </option>
              ))}
            </select>
          </label>
          <Button disabled={busy} onClick={() => void playFull(rank)}>
            {t("play")}
          </Button>
        </div>
      </PracticeRow>,
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <section
        className="page-in relative overflow-hidden rounded-2xl border border-line bg-card shadow-soft"
        data-testid="next-step"
        data-step={next.key}
      >
        <div className="flex flex-col gap-4 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 flex-col gap-1.5">
              <h2 className="text-2xl font-semibold [text-wrap:pretty]" data-testid="next-title">
                {next.title}
              </h2>
              {next.meta && <p className="text-sm font-semibold text-seal">{next.meta}</p>}
            </div>
            <div className="w-24 shrink-0 pt-1">
              {next.art === "exam" ? (
                <span className={`belt-ribbon belt-${today.exam_belt ?? me.belt} mt-3 w-full`} aria-hidden />
              ) : (
                <Diagram
                  {...ART[next.art]}
                  label={t(`art.${next.art}`)}
                  className="w-full rounded-sm drop-shadow-sm"
                />
              )}
            </div>
          </div>
          <p className="text-ink-soft">{next.body}</p>
          {next.href ? (
            <ButtonLink href={next.href} variant="primary" size="lg" data-testid="next-go">
              {next.cta}
            </ButtonLink>
          ) : (
            <Button variant="primary" size="lg" disabled={busy} onClick={next.run} data-testid="next-go">
              {next.cta}
            </Button>
          )}
          {full && dayStep >= 0 && (
            <ol className="flex items-center justify-between gap-2 border-t border-line pt-4 text-sm" data-testid="today" aria-label={t("todayTitle")}>
              {([t("stripWarmup"), t("stripGame"), t("stripLesson")] as const).map((label, i) => (
                <li key={label} className={`flex items-center gap-2 ${i === dayStep ? "font-semibold text-ink" : "text-ink-soft"}`}>
                  <span
                    className={`flex size-6 items-center justify-center rounded-full border text-xs ${i < dayStep ? "border-ok bg-ok text-paper" : i === dayStep ? "border-seal text-seal" : "border-line"}`}
                    aria-hidden
                  >
                    {i < dayStep ? <Check /> : i + 1}
                  </span>
                  <span>
                    {label}
                    {i < dayStep && <span className="sr-only"> ({t("stepDone")})</span>}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </section>

      <BeltPath me={me} today={today} done={done} total={total} onPlacement={busy ? undefined : () => void takePlacement()} />

      {practice.length > 0 && (
        <section className="flex flex-col gap-1" aria-labelledby="practice-title">
          <h2 id="practice-title" className="text-xl font-semibold">
            {t("practiceTitle")}
          </h2>
          <ul className="flex flex-col">{practice}</ul>
        </section>
      )}

      {error && (
        <p role="alert" className="text-bad">
          {error}
        </p>
      )}
    </div>
  );
}

function PracticeRow({ title, detail, children }: { title: string; detail: string; children: ReactNode }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line py-4 last:border-b-0">
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="font-semibold">{title}</span>
        <span className="text-sm text-ink-soft">{detail}</span>
      </span>
      {children}
    </li>
  );
}

/** Where the learner is on the belt path and what opens the next belt. */
function BeltPath({
  me,
  today,
  done,
  total,
  onPlacement,
}: {
  me: Me;
  today: Today;
  done: number;
  total: number;
  onPlacement?: () => void;
}) {
  const t = useTranslations("home");
  const tb = useTranslations("belts");
  const target = today.exam_belt;
  const games = Math.min(today.capture.games_played, CAPTURE_GAMES_FOR_EXAM);

  return (
    <section className="flex flex-col gap-3 rounded-2xl bg-paper-deep/70 p-5" data-testid="belt-path-home" aria-labelledby="path-title">
      <div className="flex items-center justify-between gap-3">
        <h2 id="path-title" className="flex items-center gap-2 text-lg font-semibold" data-testid="belt">
          <span className={`belt-chip belt-${me.belt}`} aria-hidden />
          {tb(me.belt as "white")}
          {me.rank_estimate !== null && me.rank_estimate !== undefined && (
            <span className="font-sans text-base font-normal text-ink-soft" data-testid="rank-estimate">
              · {rankLabel(me.rank_estimate)}
            </span>
          )}
        </h2>
        <Link href="/progress" className="py-2 text-sm text-ink-soft underline hover:text-seal" data-testid="home-progress">
          {t("progressLink")}
        </Link>
      </div>
      {target ? (
        <>
          <p className="flex items-center gap-2 text-sm">
            <span className="text-ink-soft">{t("pathNext")}</span>
            <span className={`belt-chip belt-${target}`} aria-hidden />
            <span className="font-semibold">{tb(target as "yellow")}</span>
          </p>
          {me.belt === "white" ? (
            <div className="flex flex-col gap-2 text-sm">
              <Meter label={t("pathLessons", { done, total })} value={done / Math.max(total, 1)} />
              <Meter label={t("pathCapture", { done: games, total: CAPTURE_GAMES_FOR_EXAM })} value={games / CAPTURE_GAMES_FOR_EXAM} />
              <p className="text-ink-soft">{t("pathWhiteExam")}</p>
              {today.placement_available && (
                <button
                  type="button"
                  onClick={onPlacement}
                  disabled={!onPlacement}
                  className="self-start py-2 text-left text-ink-soft underline underline-offset-4 hover:text-seal disabled:opacity-60"
                  data-testid="placement-link"
                >
                  {t("placementLink")}
                </button>
              )}
            </div>
          ) : (
            <p className="text-sm text-ink-soft">{today.exam_available ? t("pathReady") : t("examLockedBelt")}</p>
          )}
        </>
      ) : (
        <p className="text-sm text-ink-soft">{t("pathTop")}</p>
      )}
    </section>
  );
}

function Meter({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1">
      <span>{label}</span>
      <span className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
        <span className="block h-full rounded-full bg-ink" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
    </div>
  );
}

function Check() {
  return (
    <svg viewBox="0 0 12 12" className="size-3" aria-hidden>
      <path d="M2.5 6.5l2.2 2.2 4.8-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
