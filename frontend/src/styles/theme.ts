import { createTheme } from '@mui/material/styles';
import { Direction } from '@mui/material';

export const createAppTheme = (direction: Direction) => {
  return createTheme({
    direction: direction,
    palette: {
      primary: {
        main: '#1976d2',
      },
      secondary: {
        main: '#dc004e',
      },
    },
    // TODO: Add custom typography for Arabic fonts if needed
  });
};