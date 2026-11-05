import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { LessonClient } from "./LessonClient";

export default function LessonPage({ params }: PageProps<"/[locale]/lesson/[gameId]">) {
  const { locale, gameId } = use(params);
  setRequestLocale(locale);
  return <LessonClient key={gameId} gameId={gameId} />;
}
