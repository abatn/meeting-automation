import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Import translations from src to satisfy Vite's security/import rules
import en from './locales/en.json';
import fr from './locales/fr-TN.json';
import ar from './locales/ar-TN.json';

i18n
  .use(initReactI18next)
  .init({
    lng: 'en', // Force English as the starting language
    fallbackLng: 'en',
    supportedLngs: ['en', 'fr-TN', 'ar-TN'],
    debug: false,
    resources: {
      en: { translation: en },
      'fr-TN': { translation: fr },
      'ar-TN': { translation: ar },
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;