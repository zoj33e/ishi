"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { createGame, getMe, getSchool, getToday, startExam, type Locale, type Me, type School, type Today } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

type Data = { me: Me; today: Today; school: School };

export function HomeClient() {
  const t = useTranslations("home");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const errorText = useErrorText();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    Promise.all([getMe(), getToday(), getSchool(locale)])
      .then(([me, today, school]) => alive && setData({ me, today, school }))
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

  const playCapture = () => go(async () => `/play/${(await createGame()).id}`);
  const takeExam = () => go(async () => `/exam/${(await startExam()).id}`);

  if (!data) {
    return (
      <p role={error ? "alert" : "status"} className={error ? "text-bad" : "text-ink-soft"}>
        {error ?? t("starting")}
      </p>
    );
  }

  const { me, today, school } = data;
  const done = school.lessons.filter((l) => l.status === "done").length;
  const next = school.lessons.find((l) => l.id === school.next_lesson);
  const cap = today.capture;

  return (
    <div className="flex flex-col gap-4">
      <p className="self-start rounded-full border border-line bg-card px-3 py-1 text-sm font-semibold" data-testid="belt">
        {t(`belt.${me.belt === "yellow" ? "yellow" : "white"}`)}
      </p>

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

      {me.belt === "white" && (
        <Card title={t("examTitle")}>
          {today.exam_in_progress ? (
            <Link href={`/exam/${today.exam_in_progress}`} className="self-start">
              <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">
                {t("examContinue")}
              </span>
            </Link>
          ) : today.exam_available ? (
            <>
              <p>{t("examReady")}</p>
              <Button variant="primary" className="self-start" disabled={busy} onClick={() => void takeExam()}>
                {t("examStart")}
              </Button>
            </>
          ) : (
            <p className="text-ink-soft">{t("examLocked")}</p>
          )}
        </Card>
      )}

      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>
    </div>
  );
}
