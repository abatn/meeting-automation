import { renderHook, act } from '@testing-library/react';
import { useRTL } from '../../hooks/useRTL';

describe('useRTL hook', () => {
  test('should handle LTR/RTL switching', () => {
    const { result } = renderHook(() => useRTL());
    
    expect(result.current.direction).toBe('ltr');
    
    act(() => {
      result.current.setDirection('rtl');
    });
    
    expect(result.current.direction).toBe('rtl');
    expect(document.dir).toBe('rtl');
  });
});
