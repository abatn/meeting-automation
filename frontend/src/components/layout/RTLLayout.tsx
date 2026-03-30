import React, { useMemo, useEffect } from "react";
import { Box, ThemeProvider } from "@mui/material";
import rtlPlugin from "stylis-plugin-rtl";
import { CacheProvider } from "@emotion/react";
import createCache from "@emotion/cache";
import { prefixer } from "stylis";
import { useTranslation } from "react-i18next";
import { createAppTheme } from "../../styles/theme";

interface RTLLayoutProps {
  children: React.ReactNode;
}

// Create rtl cache
const cacheRtl = createCache({
  key: "muirtl",
  stylisPlugins: [prefixer, rtlPlugin],
});

const RTLLayout: React.FC<RTLLayoutProps> = ({ children }) => {
  const { i18n } = useTranslation();
  const direction = i18n.dir();

  useEffect(() => {
    document.body.dir = direction;
    document.documentElement.lang = i18n.language;
  }, [direction, i18n.language]);

  const theme = useMemo(() => createAppTheme(direction), [direction]);

  if (direction === "rtl") {
    return (
      <CacheProvider value={cacheRtl}>
        <ThemeProvider theme={theme}>
          <Box
            dir="rtl"
            sx={{ minHeight: "100vh", bgcolor: "background.default" }}
          >
            {children}
          </Box>
        </ThemeProvider>
      </CacheProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <Box dir="ltr" sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
        {children}
      </Box>
    </ThemeProvider>
  );
};

export default RTLLayout;
