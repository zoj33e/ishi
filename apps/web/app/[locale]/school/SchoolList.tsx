"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";
import { getSchool, type Locale, type School } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

export function SchoolList() {
  const t = useTranslations("school");
  const locale = useLocale() as Locale;
  const errorText = useErrorText();
  const [school, setSchool] = useState<School | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getSchool(locale)
      .then((s) => alive && setSchool(s))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [locale, errorText]);

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <Link href="/" className="py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>
      {error && <p role="alert" className="text-bad">{error}</p>}
      <ol className="flex flex-col gap-2">
        {school?.lessons.map((l) => {
          const body = (
            <div className="flex min-h-14 items-center justify-between gap-3 rounded-2xl border border-line bg-card px-4 py-3">
              <div>
                <p className="text-sm text-ink-soft">{t("lessonN", { n: l.order })}</p>
                <p className="font-semibold">{l.title}</p>
              </div>
              <div className="shrink-0 text-right text-sm">
                <p className={l.status === "done" ? "text-ok" : l.status === "locked" ? "text-ink-soft" : "font-semibold"}>
                  {t(`status.${l.status}`)}
                </p>
                {l.status !== "locked" && <p className="text-ink-soft">{t("tasksDone", { done: l.tasks_done, total: l.tasks_total })}</p>}
              </div>
            </div>
          );
          return (
            <li key={l.id} data-testid={`lesson-${l.id}`} data-status={l.status}>
              {l.status === "locked" ? (
                <div aria-disabled className="opacity-50">{body}</div>
              ) : (
                <Link href={`/school/${l.id}`}>{body}</Link>
              )}
            </li>
          );
        })}
      </ol>
    </main>
  );
}
