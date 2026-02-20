import { useCallback } from 'react';
import dayjs from 'dayjs';

export const useCulturalCalendar = () => {
  const holidays: Record<string, string> = {
    '2026-03-20': 'Independence Day (Tunisia)',
    '2026-04-09': 'Martyrs\' Day (Tunisia)',
    '2026-05-01': 'Labour Day',
    '2026-07-25': 'Republic Day (Tunisia)',
    '2026-08-13': 'Women\'s Day (Tunisia)',
    '2026-10-15': 'Evacuation Day (Tunisia)',
  };

  const isHoliday = useCallback((date: string | Date) => {
    const dateStr = dayjs(date).format('YYYY-MM-DD');
    return !!holidays[dateStr];
  }, []);

  const getHolidayName = useCallback((date: string | Date) => {
    const dateStr = dayjs(date).format('YYYY-MM-DD');
    return holidays[dateStr] || null;
  }, []);

  const formatDate = useCallback((date: Date) => {
    return dayjs(date).format('DD/MM/YYYY');
  }, []);

  return {
    isHoliday,
    getHolidayName,
    formatDate,
  };
};