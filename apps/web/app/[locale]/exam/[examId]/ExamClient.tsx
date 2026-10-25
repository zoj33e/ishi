"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { createGame, getExam, type Exam } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

/** White -> Yellow exam (D-023): win 3 capture games (9x9, first to 3, bot level 2) before losing 3. */
export function ExamClient({ examId }: { examId: string }) {
  const t = useTranslations("exam");
  const router = useRouter();
  const errorText = useErrorText();
  const [exam, setExam] = useState<Exam | null>(null);
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

  const play = async () => {
    if (!exam) return;
    setBusy(true);
    try {
      const id = exam.active_game ?? (await createGame(exam.id)).id;
      router.push(`/play/${id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <Link href="/" className="py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>
      {exam && (
        <Card>
          <p className="leading-relaxed">{t("rules")}</p>
          <p className="text-lg font-semibold" data-testid="exam-score">
            {t("score", { won: exam.games_won, lost: exam.games_lost })}
          </p>
          {exam.status === "in_progress" && (
            <Button variant="primary" className="self-start" disabled={busy} onClick={() => void play()}>
              {exam.active_game ? t("resume") : t("play")}
            </Button>
          )}
          {exam.status === "passed" && <p className="text-xl font-semibold text-ok">{t("passed")}</p>}
          {exam.status === "failed" && <p className="text-warn">{t("failed")}</p>}
        </Card>
      )}
      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>
    </main>
  );
}
