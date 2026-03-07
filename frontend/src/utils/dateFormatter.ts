import dayjs from "dayjs";
import "dayjs/locale/fr";
import "dayjs/locale/ar";
import i18n from "../i18n/config";

export const formatDate = (date: string | Date): string => {
  const locale = i18n.language.startsWith("fr")
    ? "fr"
    : i18n.language.startsWith("ar")
      ? "ar"
      : "en";
  return dayjs(date).locale(locale).format("LL");
};
