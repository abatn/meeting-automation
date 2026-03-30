import { createTheme, Direction } from "@mui/material/styles";

export const createAppTheme = (direction: Direction) => {
  return createTheme({
    direction,
    palette: {
      primary: {
        main: "#1976d2",
      },
      secondary: {
        main: "#475569", // Professional slate grey instead of aggressive red
      },
      background: {
        default: "#FAFAFA", // Noble, clean background for Glassmorphism
      },
    },
    typography: {
      fontFamily:
        direction === "rtl" 
          ? "'Noto Sans Arabic', sans-serif" 
          : "'Inter', sans-serif",
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: "none",
            borderRadius: 8,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 12,
          },
        },
      },
    },
  });
};
