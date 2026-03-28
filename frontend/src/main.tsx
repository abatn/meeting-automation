import React, { useMemo } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Provider } from "react-redux";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { LocalizationProvider } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { useTranslation } from "react-i18next";

import App from "./App";
import { store } from "./store";
import { createAppTheme } from "./styles/theme";
import "./i18n/config";
import "./styles/globals.css";

const RootApp = () => {
  const { i18n } = useTranslation();
  const theme = useMemo(() => createAppTheme(i18n.dir()), [i18n.language]);

  return (
    <ThemeProvider theme={theme}>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <CssBaseline />
        <App />
      </LocalizationProvider>
    </ThemeProvider>
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Provider store={store}>
      <BrowserRouter>
        <RootApp />
      </BrowserRouter>
    </Provider>
  </React.StrictMode>,
);
