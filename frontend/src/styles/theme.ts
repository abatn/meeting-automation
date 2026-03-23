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
        default: "#f8fafc", // Slightly lighter professional background
      },
    },
    typography: {
      fontFamily:
        direction === "rtl" ? "Roboto, Cairo, Arial" : "Roboto, Arial",
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
