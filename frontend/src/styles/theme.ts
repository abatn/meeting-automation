import { createTheme, Direction } from '@mui/material/styles';

export const createAppTheme = (direction: Direction) => {
  return createTheme({
    direction,
    palette: {
      primary: {
        main: '#1976d2',
      },
      secondary: {
        main: '#dc004e',
      },
      background: {
        default: '#f5f5f5',
      },
    },
    typography: {
      fontFamily: direction === 'rtl' ? 'Roboto, Cairo, Arial' : 'Roboto, Arial',
    },
    components: {
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
          },
        },
      },
    },
  });
};