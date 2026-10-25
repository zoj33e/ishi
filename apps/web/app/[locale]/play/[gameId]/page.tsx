import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { GameClient } from "./GameClient";

export default function PlayPage({ params }: PageProps<"/[locale]/play/[gameId]">) {
  const { locale, gameId } = use(params);
  setRequestLocale(locale);
  return <GameClient key={gameId} gameId={gameId} />;
}
