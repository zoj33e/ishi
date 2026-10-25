"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Board } from "@/components/board/Board";
import { Button } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { createGame, getGame, playMove, resignGame, type GameState } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

const THINKING_DELAY_MS = 300;

/** Capture Go against the capture bot. The backend checks every move and answers with the bot's
 *  reply in the same request. */
export function GameClient({ gameId }: { gameId: string }) {
  const t = useTranslations("play");
  const router = useRouter();
  const errorText = useErrorText();
  const [game, setGame] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [botPassed, setBotPassed] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let alive = true;
    getGame(gameId)
      .then((g) => alive && setGame(g))
      .catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [gameId, errorText]);

  const move = async (point: string) => {
    if (!game) return;
    setBusy(true);
    setError(null);
    timer.current = setTimeout(() => setThinking(true), THINKING_DELAY_MS);
    try {
      const res = await playMove(game.id, point);
      setGame(res.state);
      setBotPassed(res.bot_move === "pass");
    } catch (e) {
      setError(errorText(e));
    } finally {
      if (timer.current) clearTimeout(timer.current);
      setThinking(false);
      setBusy(false);
    }
  };

  const resign = async () => {
    if (!game || !window.confirm(t("resignConfirm"))) return;
    try {
      setGame(await resignGame(game.id));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const again = async () => {
    setBusy(true);
    try {
      const g = await createGame(game?.exam_id ?? undefined);
      router.push(`/play/${g.id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const finished = game?.status === "finished";
  const outcome = !game?.result ? null : game.result.startsWith("B") ? "won" : game.result.startsWith("W") ? "lost" : "draw";
  const target = game?.capture_target ?? 1;

  return (
    <main className="mx-auto flex max-w-md flex-col gap-3 px-4 py-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{game?.exam_id ? t("examTitle") : t("title")}</h1>
          <p className="text-ink-soft">{target === 1 ? t("goalOne") : t("goal", { target })}</p>
        </div>
        <Link href={game?.exam_id ? `/exam/${game.exam_id}` : "/"} className="shrink-0 py-1 text-ink-soft underline underline-offset-4">
          {t("home")}
        </Link>
      </header>

      {game && (
        <div className="grid grid-cols-2 gap-2 text-sm" data-testid="captures">
          <div className="rounded-xl border border-line bg-card px-3 py-2">
            <p className="text-ink-soft">{t("you")}</p>
            <p className="text-lg font-semibold">
              {t("captured")}: {game.captures.black} / {target}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card px-3 py-2">
            <p className="text-ink-soft">{t("bot", { level: game.bot_level ?? 1 })}</p>
            <p className="text-lg font-semibold">
              {t("captured")}: {game.captures.white} / {target}
            </p>
          </div>
        </div>
      )}

      <p className="min-h-6 text-ink-soft" aria-live="polite" data-testid="turn">
        {finished ? null : thinking ? t("thinking") : botPassed ? t("botPassed") : t("yourTurn")}
      </p>

      <div className={`rounded-xl shadow-sm transition-opacity ${thinking ? "opacity-80" : ""}`}>
        {game ? (
          <Board
            size={game.board_size}
            stones={game.stones}
            toMove={game.to_move}
            lastMove={game.last_move}
            interactive={!finished && !busy}
            onPlay={(p) => void move(p)}
          />
        ) : (
          <div className="aspect-square w-full rounded-xl bg-wood/60" />
        )}
      </div>

      <p role="alert" className="min-h-6 text-bad">
        {error}
      </p>

      {!finished && game && (
        <div className="flex gap-2">
          <Button onClick={() => void move("pass")} disabled={busy}>{t("pass")}</Button>
          <Button onClick={() => void resign()} disabled={busy}>{t("resign")}</Button>
        </div>
      )}

      {finished && (
        <div role="dialog" aria-labelledby="game-over" className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-4 shadow-md" data-testid="game-over" data-outcome={outcome ?? ""}>
          <p id="game-over" className={`text-2xl font-semibold ${outcome === "won" ? "text-ok" : ""}`}>
            {outcome === "won" ? t("won") : outcome === "lost" ? t("lost") : t("draw")}
          </p>
          <div className="flex flex-wrap gap-2">
            {game?.exam_id ? (
              <Link href={`/exam/${game.exam_id}`}>
                <span className="inline-flex min-h-11 items-center rounded-full bg-ink px-5 font-semibold text-paper">{t("toExam")}</span>
              </Link>
            ) : (
              <Button variant="primary" onClick={() => void again()} disabled={busy}>{t("playAgain")}</Button>
            )}
            <Link href="/">
              <span className="inline-flex min-h-11 items-center rounded-full border border-line bg-card px-5 font-semibold">{t("home")}</span>
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}
