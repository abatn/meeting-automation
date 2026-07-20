import { useSelector } from 'react-redux';
import { RootState } from '../store';

export type Feature = 
  | 'AI_ACTIONS' 
  | 'UNLIMITED_MEETINGS' 
  | 'CUSTOM_BRANDING' 
  | 'ADVANCED_REPORTS';

export const useEntitlements = () => {
  const { user } = useSelector((state: RootState) => state.auth);
  
  // We assume the backend might send the plan in the user object or we have a map
  // For now we use the role or a plan field if exists. 
  // Let's assume user.plan exists (we updated the registration to include it)
  
  const plan = user?.plan || 'GRATUIT';

  const hasFeature = (feature: Feature): boolean => {
    if (user?.role === 'system_admin') return true;

    switch (feature) {
      case 'AI_ACTIONS':
        return plan === 'PRO' || plan === 'ENTREPRISE';
      case 'UNLIMITED_MEETINGS':
        return plan === 'PRO' || plan === 'ENTREPRISE';
      case 'CUSTOM_BRANDING':
        return plan === 'PRO' || plan === 'ENTREPRISE';
      case 'ADVANCED_REPORTS':
        return plan === 'ENTREPRISE';
      default:
        return false;
    }
  };

  return { hasFeature, plan };
};