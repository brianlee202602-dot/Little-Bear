export function readJsonFromStorage<T>(key: string): T | null {
  const raw = localStorage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

export function writeJsonToStorage(key: string, value: unknown): void {
  localStorage.setItem(key, JSON.stringify(value));
}

export function removeStorageItem(key: string): void {
  localStorage.removeItem(key);
}
