type StorageScope = "local" | "session";

export function readStringFromStorage(key: string, scope: StorageScope = "local"): string | null {
  return storageForScope(scope).getItem(key);
}

export function writeStringToStorage(
  key: string,
  value: string,
  scope: StorageScope = "local",
): void {
  storageForScope(scope).setItem(key, value);
}

export function readJsonFromStorage<T>(key: string, scope: StorageScope = "local"): T | null {
  const storage = storageForScope(scope);
  const raw = storage.getItem(key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    storage.removeItem(key);
    return null;
  }
}

export function writeJsonToStorage(
  key: string,
  value: unknown,
  scope: StorageScope = "local",
): void {
  storageForScope(scope).setItem(key, JSON.stringify(value));
}

export function removeStorageItem(key: string, scope: StorageScope = "local"): void {
  storageForScope(scope).removeItem(key);
}

function storageForScope(scope: StorageScope): Storage {
  return scope === "session" ? window.sessionStorage : window.localStorage;
}
