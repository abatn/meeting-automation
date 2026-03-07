// This file will contain helpers for Tunisian/Maghreb cultural adaptations.
// For example, converting between Gregorian and Hijri calendars.

// TODO: Implement Hijri calendar conversion
export const toHijri = (date: Date): string => {
  // Placeholder
  return new Intl.DateTimeFormat("ar-TN-u-ca-islamic", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
};
