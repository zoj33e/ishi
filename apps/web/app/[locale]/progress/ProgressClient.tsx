"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui";
import { Link } from "@/i18n/navigation";
import { getProgress, type Progress } from "@/lib/api";
import { rankLabel } from "@/lib/rank";
import { useErrorText } from "@/lib/useErrorText";

/** Progress (09-ui-ux §7): rank over time, the belt path, and the concepts that cost the most. */
export function ProgressClient() {
  const t = useTranslations("progress");
  const tb = useTranslations("belts");
  const tc = useTranslations("gym.concept");
  const errorText = useErrorText();
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    getProgress()
      .then((p) => alive && setData(p))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [errorText]);

  const maxCount = Math.max(1, ...(data?.concept_stats.map((c) => c.count) ?? []));

  return (
    <main className="mx-auto flex max-w-md flex-col gap-4 px-4 py-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <Link href="/" className="py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>
      {!data && (
        <p role={error ? "alert" : "status"} className={error ? "text-bad" : "text-ink-soft"}>
          {error ?? t("loading")}
        </p>
      )}
      {data && (
        <>
          <Card>
            <p className="text-sm text-ink-soft">{tb(data.belt as "white")}</p>
            <p className="text-3xl font-semibold" data-testid="rank-now">
              {data.rank_label ?? t("noRank")}
            </p>
            <p className="text-sm text-ink-soft">
              {data.rank_label ? t("rankNote", { games: data.games_played }) : t("noRankNote")}
            </p>
            <p className="text-sm text-ink-soft" data-testid="bot-now">
              {t("botNow", { bot: data.bot_label })}
            </p>
          </Card>

          <Card title={t("chartTitle")}>
            {data.rank_history.length > 0 ? (
              <RankChart points={data.rank_history.map((p) => ({ date: p.date, rank: p.rank_estimate }))} label={t("chartLabel")} />
            ) : (
              <p className="text-ink-soft">{t("chartEmpty")}</p>
            )}
          </Card>

          <Card title={t("beltsTitle")}>
            <ol className="flex flex-col gap-2" data-testid="belt-path">
              {data.belts.map((b) => (
                <li key={b.belt} className="flex items-center gap-3" data-status={b.status}>
                  <span className={`belt-chip belt-${b.belt} ${b.status === "later" || b.status === "next" ? "opacity-40" : ""}`} aria-hidden />
                  <span className={b.status === "current" ? "font-semibold" : b.status === "done" ? "" : "text-ink-soft"}>
                    {tb(b.belt as "white")}
                    {b.rank !== null && b.rank !== undefined && <span className="text-sm text-ink-soft"> · {rankLabel(b.rank)}</span>}
                  </span>
                  <span className="ml-auto text-sm text-ink-soft">{t(`beltStatus.${b.status}`)}</span>
                </li>
              ))}
            </ol>
            {data.exam.belt_target && (
              <div className="flex flex-col gap-2 border-t border-line pt-3" data-testid="exam-status">
                {data.exam.in_progress ? (
                  <Link href={`/exam/${data.exam.in_progress}`} className="self-start">
                    <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("examContinue")}</span>
                  </Link>
                ) : data.exam.available ? (
                  <p className="font-semibold text-ok">{t("examReady", { belt: tb(data.exam.belt_target as "white") })}</p>
                ) : data.exam.rank_needed !== null && data.exam.rank_needed !== undefined ? (
                  <p className="text-sm text-ink-soft">
                    {data.rank_estimate !== null && data.rank_estimate !== undefined && data.rank_estimate <= data.exam.rank_needed
                      ? t("examNeedsGames", {
                          belt: tb(data.exam.belt_target as "white"),
                          games: data.exam.games_left,
                        })
                      : t("examNeeds", {
                      belt: tb(data.exam.belt_target as "white"),
                      rank: rankLabel(data.exam.rank_needed),
                      games: data.exam.games_left,
                    })}
                  </p>
                ) : null}
              </div>
            )}
          </Card>

          <Card title={t("conceptsTitle")}>
            {data.concept_stats.length > 0 ? (
              <ul className="flex flex-col gap-2" data-testid="concept-stats">
                {data.concept_stats.map((c) => (
                  <li key={c.concept_id} className="flex flex-col gap-1">
                    <span className="flex justify-between text-sm">
                      <span>{tc(c.concept_id as "missed_capture")}</span>
                      <span className="text-ink-soft">{t("times", { n: c.count })}</span>
                    </span>
                    <span className="h-2 overflow-hidden rounded-full bg-line" aria-hidden>
                      <span className="block h-full rounded-full bg-warn" style={{ width: `${(c.count / maxCount) * 100}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-ink-soft">{t("conceptsEmpty")}</p>
            )}
          </Card>
        </>
      )}
    </main>
  );
}

/** Rank over time; stronger is up (smaller kyu number at the top). */
function RankChart({ points, label }: { points: { date: string; rank: number }[]; label: string }) {
  const W = 300;
  const H = 140;
  const PAD = { l: 34, r: 8, t: 10, b: 20 };
  const ranks = points.map((p) => p.rank);
  const lo = Math.floor(Math.min(...ranks) - 1);
  const hi = Math.ceil(Math.max(...ranks) + 1);
  const x = (i: number) => PAD.l + (points.length === 1 ? (W - PAD.l - PAD.r) / 2 : (i / (points.length - 1)) * (W - PAD.l - PAD.r));
  const y = (r: number) => PAD.t + ((r - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const ticks = [lo, Math.round((lo + hi) / 2), hi];
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.rank).toFixed(1)}`).join(" ");
  const last = points[points.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${label}: ${rankLabel(last.rank)}`} data-testid="rank-chart">
      {ticks.map((r) => (
        <g key={r}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(r)} y2={y(r)} stroke="var(--line)" strokeWidth="1" />
          <text x={PAD.l - 6} y={y(r) + 4} textAnchor="end" fontSize="10" fill="var(--ink-soft)">
            {rankLabel(r)}
          </text>
        </g>
      ))}
      <path d={path} fill="none" stroke="var(--ok)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) => (
        <circle key={p.date} cx={x(i)} cy={y(p.rank)} r="3.5" fill="var(--card)" stroke="var(--ok)" strokeWidth="2" />
      ))}
      <text x={PAD.l} y={H - 4} fontSize="10" fill="var(--ink-soft)">
        {points[0].date.slice(5)}
      </text>
      {points.length > 1 && (
        <text x={W - PAD.r} y={H - 4} fontSize="10" textAnchor="end" fill="var(--ink-soft)">
          {last.date.slice(5)}
        </text>
      )}
    </svg>
  );
}
