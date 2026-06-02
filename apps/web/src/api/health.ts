import { requestRaw } from "./http";

export async function getLiveStatus(): Promise<unknown> {
  const response = await requestRaw("/health/live", { method: "GET" });
  if (!response.ok) {
    throw new Error(`health request failed: ${response.status}`);
  }
  return response.json();
}
