import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { ExamClient } from "./ExamClient";

export default function ExamPage({ params }: PageProps<"/[locale]/exam/[examId]">) {
  const { locale, examId } = use(params);
  setRequestLocale(locale);
  return <ExamClient examId={examId} />;
}
