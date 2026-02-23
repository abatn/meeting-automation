import { renderHook } from '@testing-library/react';
import { useRTL } from '../../hooks/useRTL';

// Mock react-i18next
jest.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: {
      dir: () => 'ltr',
    },
  }),
}));

describe('useRTL hook', () => {
  test('should return direction from i18n', () => {
    const { result } = renderHook(() => useRTL());
    
    expect(result.current.dir).toBe('ltr');
    expect(result.current.isRTL).toBe(false);
  });
});