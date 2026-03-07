import { useTranslation } from "react-i18next";

export const useRTL = () => {
  const { i18n } = useTranslation();
  const isRTL = i18n.dir() === "rtl";
  return { isRTL, dir: i18n.dir() };
};
