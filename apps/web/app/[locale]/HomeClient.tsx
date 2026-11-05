"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import {
  createGame,
  getBotRanks,
  getMe,
  getSchool,
  getToday,
  startExam,
  type BotRanks,
  type Locale,
  type Me,
  type School,
  type Today,
} from "@/lib/api";
import { rankLabel } from "@/lib/rank";
import { useErrorText } from "@/lib/useErrorText";

type Data = { me: Me; today: Today; school: School; ranks: BotRanks };

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
      .then(([me, today, school, ranks]) => alive && setData({ me, today, school, ranks }))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [locale, errorText]);

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

  if (!data) {
    return (
      <p role={error ? "alert" : "status"} className={error ? "text-bad" : "text-ink-soft"}>
        {error ?? t("starting")}
      </p>
    );
  }

  const { me, today, school, ranks } = data;
  const rank = botRank ?? ranks.recommended;
  const rankOptions = [...new Set([...ranks.ranks, ranks.recommended])].sort((a, b) => b - a);
  const full = today.game.mode === "full";
  const examBelt = today.exam_belt ? tb(today.exam_belt as "yellow") : "";
  const done = school.lessons.filter((l) => l.status === "done").length;
  const next = school.lessons.find((l) => l.id === school.next_lesson);
  const cap = today.capture;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1 text-sm font-semibold" data-testid="belt">
          <span className={`belt-chip belt-${me.belt}`} aria-hidden />
          {tb(me.belt as "white")}
          {me.rank_estimate !== null && me.rank_estimate !== undefined && (
            <span className="font-normal text-ink-soft" data-testid="rank-estimate">· {rankLabel(me.rank_estimate)}</span>
          )}
        </p>
        <Link href="/progress" className="py-1 text-ink-soft underline underline-offset-4" data-testid="home-progress">
          {t("progressLink")}
        </Link>
      </div>

      {full && (
        <Card title={t("todayTitle")}>
          <ol className="flex flex-col gap-3" data-testid="today">
            <TodayStep n={1} done={today.warmup_due === 0} label={t("todayWarmup", { n: today.warmup_due })}>
              {today.warmup_due > 0 && (
                <Link href="/gym?warmup=1" data-testid="today-warmup">
                  <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("gymWarmup")}</span>
                </Link>
              )}
            </TodayStep>
            <TodayStep n={2} done={false} label={t("todayGame", { bot: rankLabel(ranks.recommended) })}>
              {today.warmup_due === 0 && !today.lesson_game && (
                <Button variant="primary" disabled={busy} onClick={() => void playFull(ranks.recommended)} data-testid="today-play">
                  {t("fullPlay")}
                </Button>
              )}
            </TodayStep>
            <TodayStep n={3} done={false} label={today.lesson_game ? t("todayLessonReady") : t("todayLesson")}>
              {today.lesson_game && (
                <Link href={`/lesson/${today.lesson_game}`} data-testid="today-lesson">
                  <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("lessonOpen")}</span>
                </Link>
              )}
            </TodayStep>
          </ol>
        </Card>
      )}

      {today.lesson_game && !full && (
        <Card title={t("lessonTitle")}>
          <p className="text-ink-soft">{t("lessonReady")}</p>
          <Link href={`/lesson/${today.lesson_game}`} className="self-start" data-testid="home-lesson">
            <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("lessonOpen")}</span>
          </Link>
        </Card>
      )}

      <Card title={t("gymTitle")}>
        <p className="text-ink-soft" data-testid="gym-due">{t("gymDue", { n: today.warmup_due })}</p>
        <div className="flex flex-wrap gap-2">
          {today.warmup_due > 0 && (
            <Link href="/gym?warmup=1" data-testid="home-warmup">
              <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("gymWarmup")}</span>
            </Link>
          )}
          <Link href="/gym" data-testid="home-gym">
            <span className="inline-flex min-h-11 items-center rounded-full border border-line bg-card px-5 font-semibold">{t("gymOpen")}</span>
          </Link>
        </div>
      </Card>

      <Card title={t("schoolTitle")}>
        <p className="text-ink-soft">{t("schoolProgress", { done, total: school.lessons.length })}</p>
        <div className="h-2 overflow-hidden rounded-full bg-line" aria-hidden>
          <div className="h-full bg-ok" style={{ width: `${(done / school.lessons.length) * 100}%` }} />
        </div>
        {next ? (
          <Link href={`/school/${next.id}`} className="self-start">
            <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">
              {t("schoolContinue", { title: next.title })}
            </span>
          </Link>
        ) : (
          <p className="font-semibold text-ok">{t("schoolDone")}</p>
        )}
        <Link href="/school" className="self-start py-1 text-ink-soft underline underline-offset-4">
          {t("schoolOpen")}
        </Link>
      </Card>

      <Card title={t("captureTitle")}>
        <p className="text-ink-soft">
          {t("captureInfo", { stage: cap.stage, total: cap.stages_total, size: cap.board_size, target: cap.capture_target })}
        </p>
        <p className="text-sm text-ink-soft">{t("captureStreak", { streak: cap.streak })}</p>
        <Button variant={next ? "secondary" : "primary"} className="self-start" disabled={busy} onClick={() => void playCapture()}>
          {t("capturePlay")}
        </Button>
      </Card>

      <Card title={t("fullTitle")}>
        {ranks.unlocked ? (
          <>
            <p className="text-ink-soft">{t("fullInfo")}</p>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2">
                <span>{t("fullStrength")}</span>
                <select
                  className="min-h-11 rounded-lg border border-line bg-card px-2"
                  value={rank}
                  onChange={(e) => setBotRank(Number(e.target.value))}
                  data-testid="bot-rank"
                >
                  {rankOptions.map((r) => (
                    <option key={r} value={r}>
                      {r === ranks.recommended ? t("fullRecommended", { rank: rankLabel(r) }) : rankLabel(r)}
                    </option>
                  ))}
                </select>
              </label>
              <Button variant="primary" disabled={busy} onClick={() => void playFull(rank)}>
                {t("fullPlay")}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-ink-soft">{t("fullLocked")}</p>
        )}
      </Card>

      {today.exam_belt && (
        <Card title={t("examTitle", { belt: examBelt })}>
          {today.exam_in_progress ? (
            <Link href={`/exam/${today.exam_in_progress}`} className="self-start">
              <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">
                {t("examContinue")}
              </span>
            </Link>
          ) : today.exam_available ? (
            <>
              <p>{me.belt === "white" ? t("examReady") : t("examReadyBelt")}</p>
              <Button variant="primary" className="self-start" disabled={busy} onClick={() => void takeExam()}>
                {t("examStart")}
              </Button>
            </>
          ) : (
            <p className="text-ink-soft">{me.belt === "white" ? t("examLocked") : t("examLockedBelt")}</p>
          )}
        </Card>
      )}

      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>
    </div>
  );
}

function TodayStep({ n, done, label, children }: { n: number; done: boolean; label: string; children?: React.ReactNode }) {
  return (
    <li className="flex flex-wrap items-center gap-3">
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${done ? "bg-ok text-paper" : "border border-line"}`}
        aria-hidden
      >
        {done ? "✓" : n}
      </span>
      <span className={`flex-1 ${done ? "text-ink-soft line-through" : ""}`}>{label}</span>
      {children}
    </li>
  );
}
