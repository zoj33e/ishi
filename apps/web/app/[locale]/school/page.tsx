import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { SchoolList } from "./SchoolList";

export default function SchoolPage({ params }: PageProps<"/[locale]/school">) {
  const { locale } = use(params);
  setRequestLocale(locale);
  return <SchoolList />;
}
