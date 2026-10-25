"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Board, type Mark } from "@/components/board/Board";
import { Button } from "@/components/ui";
import { Link, useRouter } from "@/i18n/navigation";
import { createGame, getGame, playMove, resignGame, type GameState } from "@/lib/api";
import { useErrorText } from "@/lib/useErrorText";

const THINKING_DELAY_MS = 300;

/** Capture Go (capture bot) and full 9x9 games (HumanSL bot). The backend checks every move and
 *  answers with the bot's reply in the same request; after two passes it scores a 9x9 game. */
export function GameClient({ gameId }: { gameId: string }) {
  const t = useTranslations("play");
  const router = useRouter();
  const errorText = useErrorText();
  const [game, setGame] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [botPassed, setBotPassed] = useState(false);
  const [botResigned, setBotResigned] = useState(false);
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
      setBotResigned(res.bot_move === "resign");
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
      const g = await createGame(
        full ? { mode: "full", bot_rank: game?.bot_rank ?? null } : { mode: "capture", exam_id: game?.exam_id ?? null },
      );
      router.push(`/play/${g.id}`);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const finished = game?.status === "finished";
  const full = game?.mode === "full";
  const outcome = !game?.result ? null : game.result.startsWith("B") ? "won" : game.result.startsWith("W") ? "lost" : "draw";
  const target = game?.capture_target ?? 1;
  const pointsRaw = game?.result?.match(/^[BW]\+(\d+(?:\.\d+)?)$/)?.[1];
  const points = pointsRaw && String(Number(pointsRaw)); // "88.0" -> "88", "6.5" stays
  const resultText = (() => {
    if (!game?.result) return "";
    if (game.result === "B+R") return botResigned || full ? t("botResigned") : t("won");
    if (game.result === "W+R") return t("youResigned");
    if (full && points) return outcome === "won" ? t("wonBy", { points }) : t("lostBy", { points });
    return outcome === "won" ? t("won") : outcome === "lost" ? t("lost") : t("draw");
  })();
  const deadMarks: Mark[] = (game?.dead ?? []).map((p) => ({ point: p, kind: "cross" }));

  return (
    <main className="mx-auto flex max-w-md flex-col gap-3 px-4 py-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{!game ? " " : game.exam_id ? t("examTitle") : full ? t("fullTitle") : t("title")}</h1>
          <p className="text-ink-soft">
            {!game ? " " : full ? t("fullGoal", { komi: game.komi }) : target === 1 ? t("goalOne") : t("goal", { target })}
          </p>
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
              {t("captured")}: {game.captures.black}
              {full ? "" : ` / ${target}`}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-card px-3 py-2">
            <p className="text-ink-soft">
              {full ? t("botRank", { rank: game.bot_label ?? "" }) : t("bot", { level: game.bot_level ?? 1 })}
            </p>
            <p className="text-lg font-semibold">
              {t("captured")}: {game.captures.white}
              {full ? "" : ` / ${target}`}
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
            marks={finished ? deadMarks : []}
            territory={finished ? game.score?.territory : undefined}
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

      {!finished && full && <p className="text-sm text-ink-soft">{t("fullHint")}</p>}

      {!finished && game && (
        <div className="flex gap-2">
          <Button onClick={() => void move("pass")} disabled={busy}>{t("pass")}</Button>
          <Button onClick={() => void resign()} disabled={busy}>{t("resign")}</Button>
        </div>
      )}

      {finished && (
        <div role="dialog" aria-labelledby="game-over" className="flex flex-col gap-3 rounded-2xl border border-line bg-card p-4 shadow-md" data-testid="game-over" data-outcome={outcome ?? ""}>
          <p id="game-over" className={`text-2xl font-semibold ${outcome === "won" ? "text-ok" : ""}`}>
            {resultText}
          </p>
          {game?.score && (
            <p className="text-sm text-ink-soft" data-testid="score-line">
              {t("scoreLine", { black: game.score.black_area, white: game.score.white_area, komi: game.score.komi })}
              {deadMarks.length > 0 && <> · {t("deadNote")}</>}
            </p>
          )}
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
