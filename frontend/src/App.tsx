import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useEffect } from 'react';
import { useRTL } from './hooks/useRTL';
import RTLLayout from './components/layout/RTLLayout';

function App() {
  const { i18n } = useTranslation();
  const isRTL = useRTL();

  useEffect(() => {
    document.dir = isRTL ? 'rtl' : 'ltr';
  }, [isRTL]);

  const MainLayout = isRTL ? RTLLayout : ({ children }: { children: React.ReactNode }) => <>{children}</>;

  return (
    <MainLayout>
      <Routes>
        {/* TODO: Add routes for login, meetings, actions, reports */}
        <Route path="/" element={<h1>{i18n.t('welcome')}</h1>} />
      </Routes>
    </MainLayout>
  );
}

export default App;