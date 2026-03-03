import { renderHook } from '@testing-library/react';
import { useRTL } from '../../hooks/useRTL';
import { useTranslation } from 'react-i18next';

// Mock react-i18next
jest.mock('react-i18next', () => ({
  useTranslation: jest.fn(),
}));

describe('useRTL hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should return ltr and false for isRTL when direction is ltr', () => {
    (useTranslation as jest.Mock).mockReturnValue({
      i18n: { dir: () => 'ltr' },
    });

    const { result } = renderHook(() => useRTL());
    
    expect(result.current.dir).toBe('ltr');
    expect(result.current.isRTL).toBe(false);
  });

  test('should return rtl and true for isRTL when direction is rtl', () => {
    (useTranslation as jest.Mock).mockReturnValue({
      i18n: { dir: () => 'rtl' },
    });

    const { result } = renderHook(() => useRTL());
    
    expect(result.current.dir).toBe('rtl');
    expect(result.current.isRTL).toBe(true);
  });
});
