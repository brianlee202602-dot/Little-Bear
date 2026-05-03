const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getLiveStatus(): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/health/live`);
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return response.json();
}
