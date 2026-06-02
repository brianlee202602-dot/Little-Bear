import { requestJson, requestVoid } from "./http";
import type { CurrentUserResponse, LoginRequest, TokenResponse } from "./types";

export type { CurrentUserData, CurrentUserResponse, LoginRequest, TokenResponse } from "./types";

export async function createSession(payload: LoginRequest): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/internal/v1/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function refreshSession(refreshToken: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>(
    "/internal/v1/token-refreshes",
    {
      method: "POST",
    },
    refreshToken,
  );
}

export async function deleteCurrentSession(accessToken: string): Promise<void> {
  await requestVoid(
    "/internal/v1/sessions/current",
    {
      method: "DELETE",
    },
    accessToken,
  );
}

export async function getCurrentUser(accessToken: string): Promise<CurrentUserResponse> {
  return requestJson<CurrentUserResponse>(
    "/internal/v1/users/me",
    {
      method: "GET",
    },
    accessToken,
  );
}
