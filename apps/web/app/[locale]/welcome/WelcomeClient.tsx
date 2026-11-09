"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { Diagram, type DiagramStone } from "@/components/Diagram";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { TeacherMark } from "@/components/TeacherMark";
import { Button } from "@/components/ui";
import { useRouter } from "@/i18n/navigation";
import { getSchool, patchMe, startPlacement, type Locale } from "@/lib/api";

const GAME: DiagramStone[] = [
  { at: [2, 2], color: "b" },
  { at: [6, 6], color: "w" },
  { at: [6, 2], color: "b" },
  { at: [2, 6], color: "w" },
  { at: [5, 3], color: "b" },
  { at: [3, 5], color: "w" },
  { at: [4, 4], color: "b" },
];

const CAPTURE: DiagramStone[] = [
  { at: [1, 2], color: "b" },
  { at: [2, 1], color: "b" },
  { at: [3, 2], color: "b" },
  { at: [2, 2], color: "w", ghost: true },
  { at: [2, 3], color: "b", mark: "triangle" },
];

const STEPS = 3;

/** First launch (PRD flow 1): what Go is, how Ishi teaches, then straight into lesson 1.
 *  A player who already knows Go takes the placement test instead (D-068). */
export function WelcomeClient() {
  const t = useTranslations("welcome");
  const ta = useTranslations("app");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);

  const placement = async () => {
    setBusy(true);
    await patchMe({ settings: { welcomed: true } }).catch(() => undefined);
    const exam = await startPlacement().catch(() => null);
    router.push(exam ? `/exam/${exam.id}` : "/");
  };

  const finish = async (start: boolean) => {
    setBusy(true);
    await patchMe({ settings: { welcomed: true } }).catch(() => undefined);
    if (start) {
      const school = await getSchool(locale).catch(() => null);
      const first = school?.next_lesson ?? school?.lessons[0]?.id;
      if (first) {
        router.push(`/school/${first}`);
        return;
      }
    }
    router.push("/");
  };

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col px-4 pb-6 pt-5">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <TeacherMark className="size-9" />
          <span className="font-serif text-xl font-semibold">{ta("name")}</span>
        </div>
        {step === 0 ? (
          <LocaleSwitcher />
        ) : (
          <Button variant="quiet" disabled={busy} onClick={() => void finish(false)} data-testid="welcome-skip">
            {t("skip")}
          </Button>
        )}
      </header>

      <section key={step} className="page-in flex flex-1 flex-col justify-center gap-6 py-6" aria-live="polite">
        {step === 0 && (
          <>
            <Diagram stones={GAME} animate label={t("d1Label")} className="mx-auto w-full max-w-76 drop-shadow-sm" />
            <div className="flex flex-col gap-3">
              <h1 className="text-3xl font-semibold">{t("s1Title")}</h1>
              <p className="text-ink-soft">{t("s1Body")}</p>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <Diagram stones={CAPTURE} view={[0, 0, 4, 4]} animate label={t("d2Label")} className="mx-auto w-full max-w-64 drop-shadow-sm" />
            <div className="flex flex-col gap-3">
              <h1 className="text-3xl font-semibold">{t("s2Title")}</h1>
              <p className="text-ink-soft">{t("s2Body")}</p>
              <p className="border-t border-line pt-3 text-sm text-ink-soft">{t("s2Caption")}</p>
            </div>
          </>
        )}
        {step === 2 && (
          <div className="flex flex-col gap-5">
            <h1 className="text-3xl font-semibold">{t("s3Title")}</h1>
            <p className="text-ink-soft">{t("s3Body")}</p>
            <ol className="flex flex-col" aria-label={t("dayLabel")}>
              {(["day1", "day2", "day3"] as const).map((k, i) => (
                <li key={k} className="relative flex items-center gap-4 py-3">
                  {i < 2 && <span className="absolute left-4.5 top-[calc(50%+18px)] h-[calc(100%-36px)] w-px -translate-x-1/2 bg-line" aria-hidden />}
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-card font-serif font-semibold" aria-hidden>
                    {i + 1}
                  </span>
                  <span className="flex flex-col">
                    <span className="font-semibold">{t(`${k}Title`)}</span>
                    <span className="text-sm text-ink-soft">{t(`${k}Time`)}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      <footer className="flex flex-col gap-4">
        <div className="flex items-center justify-center gap-2" role="img" aria-label={t("stepOf", { n: step + 1, total: STEPS })}>
          {Array.from({ length: STEPS }, (_, i) => (
            <span
              key={i}
              className={`size-2 rounded-full transition-colors duration-150 ${i === step ? "bg-seal" : "bg-line"}`}
            />
          ))}
        </div>
        {step < STEPS - 1 ? (
          <Button variant="primary" size="lg" onClick={() => setStep(step + 1)} data-testid="welcome-next">
            {t("next")}
          </Button>
        ) : (
          <Button variant="primary" size="lg" disabled={busy} onClick={() => void finish(true)} data-testid="welcome-start">
            {t("start")}
          </Button>
        )}
        <div className="flex min-h-11 justify-center">
          {step > 0 && (
            <Button variant="quiet" onClick={() => setStep(step - 1)}>
              {t("back")}
            </Button>
          )}
          {step === 0 && (
            <Button variant="quiet" disabled={busy} onClick={() => void placement()} data-testid="welcome-skip-first">
              {t("knowGo")}
            </Button>
          )}
        </div>
      </footer>
    </main>
  );
}
