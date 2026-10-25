import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { LessonPlayer } from "./LessonPlayer";

export default function LessonPage({ params }: PageProps<"/[locale]/school/[lessonId]">) {
  const { locale, lessonId } = use(params);
  setRequestLocale(locale);
  return <LessonPlayer key={lessonId} lessonId={lessonId} />;
}
