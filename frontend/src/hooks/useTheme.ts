import { useState, useEffect, useCallback } from 'react';

export type Theme = 'dark' | 'light';

// Module-level singleton — session-only, no localStorage
let _theme: Theme = 'dark';
const _listeners = new Set<() => void>();

const notifyListeners = () => _listeners.forEach((l) => l());

export const useTheme = (): { theme: Theme; toggleTheme: () => void } => {
  const [theme, setTheme] = useState<Theme>(_theme);

  useEffect(() => {
    const listener = () => setTheme(_theme);
    _listeners.add(listener);
    return () => {
      _listeners.delete(listener);
    };
  }, []);

  const toggleTheme = useCallback(() => {
    _theme = _theme === 'dark' ? 'light' : 'dark';
    document.documentElement.classList.toggle('light', _theme === 'light');
    notifyListeners();
  }, []);

  return { theme, toggleTheme };
};
