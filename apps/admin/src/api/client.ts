const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function getReadyStatus(): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/health/ready`);
  if (!response.ok) {
    throw new Error(`ready request failed: ${response.status}`);
  }
  return response.json();
}
