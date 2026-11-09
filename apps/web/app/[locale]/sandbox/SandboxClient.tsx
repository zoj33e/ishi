"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { Board } from "@/components/board/Board";
import { Link } from "@/i18n/navigation";
import { ApiError, fetchSandboxState, type SandboxState } from "@/lib/api";

const SIZES = [9, 13, 19, 7] as const;
const KOMI = 7;

/** Debug page (M1): local two-player game. The backend replays the move list and is the only
 *  judge of legality; this page never decides whether a move is allowed. */
export function SandboxClient() {
  const t = useTranslations("sandbox");
  const te = useTranslations("errors");
  const [size, setSize] = useState<number>(9);
  const [moves, setMoves] = useState<string[]>([]);
  const [data, setData] = useState<SandboxState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [coords, setCoords] = useState(true);

  const describe = useCallback(
    (e: unknown) => {
      if (!(e instanceof ApiError)) return te("invalid_request");
      const reason = e.detail.details?.reason;
      if (e.detail.code === "ILLEGAL_MOVE" && typeof reason === "string") {
        return te(`reason.${reason}` as "reason.ko");
      }
      return te(e.detail.message_key.replace(/^errors\./, "") as "network");
    },
    [te],
  );

  const submit = useCallback(
    async (nextMoves: string[], nextSize = size) => {
      setBusy(true);
      try {
        const res = await fetchSandboxState({ board_size: nextSize, komi: KOMI, moves: nextMoves });
        setData(res);
        setMoves(nextMoves);
        setSize(nextSize);
        setError(null);
      } catch (e) {
        setError(describe(e));
      } finally {
        setBusy(false);
      }
    },
    [describe, size],
  );

  // Load the empty board once on mount.
  useEffect(() => {
    let alive = true;
    fetchSandboxState({ board_size: 9, komi: KOMI, moves: [] })
      .then((res) => alive && setData(res))
      .catch((e: unknown) => alive && setError(describe(e)));
    return () => {
      alive = false;
    };
  }, [describe]);

  const s = data?.state;
  const finished = s?.status === "finished";

  const downloadSgf = () => {
    if (!data) return;
    const url = URL.createObjectURL(new Blob([data.sgf], { type: "application/x-go-sgf" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `ishi-sandbox-${size}x${size}.sgf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="mx-auto flex max-w-xl flex-col gap-4 px-4 py-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{t("title")}</h1>
          <p className="text-ink-soft">{t("subtitle")}</p>
        </div>
        <Link href="/" className="shrink-0 py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>

      {s && (
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft" aria-live="polite">
          <span className="font-semibold text-ink">
            {finished ? t("finished", { result: s.result ?? "" }) : t("toMove", { color: t(`color.${s.to_move}`) })}
          </span>
          <span>{t("moveNumber", { n: s.move_number })}</span>
          <span>{t("captures", { black: s.captures.black, white: s.captures.white })}</span>
        </p>
      )}

      <div className={`rounded-xl shadow-sm transition-opacity ${busy ? "opacity-90" : ""}`}>
        {s ? (
          <Board
            size={s.board_size}
            stones={s.stones}
            toMove={s.to_move}
            lastMove={s.last_move}
            showCoordinates={coords}
            interactive={!finished && !busy}
            territory={finished ? data?.score?.territory : undefined}
            onPlay={(p) => void submit([...moves, p])}
          />
        ) : (
          <div className="aspect-square w-full rounded-xl bg-wood/60" />
        )}
      </div>

      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void submit([...moves, "pass"])} disabled={busy || finished}>
          {t("pass")}
        </Button>
        <Button onClick={() => void submit(moves.slice(0, -1))} disabled={busy || moves.length === 0}>
          {t("undo")}
        </Button>
        <Button onClick={downloadSgf} disabled={!data}>
          {t("downloadSgf")}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <label className="flex items-center gap-2">
          <span>{t("size")}</span>
          <select
            className="min-h-11 rounded-lg border border-line bg-card px-2"
            value={size}
            onChange={(e) => void submit([], Number(e.target.value))}
          >
            {SIZES.map((n) => (
              <option key={n} value={n}>
                {n}×{n}
              </option>
            ))}
          </select>
        </label>
        <Button onClick={() => void submit([], size)} disabled={busy}>
          {t("newGame")}
        </Button>
        <label className="flex min-h-11 items-center gap-2">
          <input type="checkbox" className="h-5 w-5" checked={coords} onChange={(e) => setCoords(e.target.checked)} />
          {t("coordinates")}
        </label>
      </div>

      {finished && data?.score && (
        <p className="text-sm text-ink-soft">
          {t("area", { black: data.score.black_area, white: data.score.white_area })} · {t("areaNote", { komi: data.score.komi })}
        </p>
      )}
    </main>
  );
}

function Button({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className="min-h-11 rounded-control border border-line bg-card px-4 font-semibold transition-colors duration-150 hover:border-ink-soft disabled:opacity-40"
      {...props}
    >
      {children}
    </button>
  );
}
