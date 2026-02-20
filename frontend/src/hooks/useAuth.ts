import { useSelector } from 'react-redux';
import { RootState } from '../store';

export const useAuth = () => {
  const { isAuthenticated, user } = useSelector((state: RootState) => state.auth);
  return { isAuthenticated, user };
};