import { useTranslation } from 'react-i18next';
import { useMemo } from 'react';
import dayjs from 'dayjs';
import 'dayjs/locale/ar-tn';
import 'dayjs/locale/fr';

// TODO: Add more cultural calendar logic (e.g., Islamic Hijri calendar)
export const useCulturalCalendar = () => {
  const { i18n } = useTranslation();

  const locale = useMemo(() => {
    switch (i18n.language) {
      case 'ar-TN':
        return 'ar-tn';
      case 'fr-TN':
        return 'fr';
      default:
        return 'en';
    }
  }, [i18n.language]);

  const formatDate = (date: Date) => {
    return dayjs(date).locale(locale).format('LL');
  };

  return { formatDate };
};