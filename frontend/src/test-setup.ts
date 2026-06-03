/**
 * Global test setup for Vitest with Angular.
 * Provides a localStorage mock compatible with Node 26+,
 * where the native (experimental) localStorage is undefined.
 */

// Only mock if the native localStorage is broken/unavailable
if (typeof localStorage === 'undefined' || localStorage === null) {
  const _store: Record<string, string> = {};
  const mockLocalStorage: Storage = {
    getItem: (key: string) => _store[key] ?? null,
    setItem: (key: string, value: string) => { _store[key] = String(value); },
    removeItem: (key: string) => { delete _store[key]; },
    clear: () => { Object.keys(_store).forEach(k => delete _store[k]); },
    key: (index: number) => Object.keys(_store)[index] ?? null,
    get length() { return Object.keys(_store).length; },
  };
  Object.defineProperty(globalThis, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
    configurable: true,
  });
}
