"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { fetchHealth, type Health } from "@/lib/api";

type Row = { key: "api" | "engine" | "llm" | "db"; status: string };

const DOT: Record<string, string> = {
  ok: "bg-ok",
  disabled: "bg-warn",
  down: "bg-bad",
  checking: "bg-line",
};

export function HealthStatus() {
  const t = useTranslations("health");
  const [health, setHealth] = useState<Health | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await fetchHealth();
        if (alive) {
          setHealth(h);
          setUnreachable(false);
        }
      } catch {
        if (alive) setUnreachable(true);
      }
    };
    void poll();
    const timer = setInterval(poll, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const rows: Row[] = (["api", "engine", "llm", "db"] as const).map((key) => ({
    key,
    status: unreachable ? "down" : (health?.[key] ?? "checking"),
  }));

  return (
    <section className="rounded-2xl border border-line bg-card p-4" aria-live="polite">
      <h2 className="mb-3 font-semibold">{t("title")}</h2>
      <ul className="flex flex-col gap-2">
        {rows.map(({ key, status }) => (
          <li key={key} className="flex items-center justify-between gap-3">
            <span>{t(key)}</span>
            <span className="flex items-center gap-2 text-ink-soft">
              <span className={`h-2.5 w-2.5 rounded-full ${DOT[status]}`} />
              {t(`status.${status}` as "status.ok")}
            </span>
          </li>
        ))}
      </ul>
      {unreachable && <p className="mt-3 text-bad">{t("unreachable")}</p>}
      {!unreachable && health?.engine === "down" && (
        <p className="mt-3 text-warn">{t("engineOffline")}</p>
      )}
    </section>
  );
}
