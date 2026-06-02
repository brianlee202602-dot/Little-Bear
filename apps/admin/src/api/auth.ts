import { requestJson, requestVoid } from "./http";
import type {
  AdminCurrentUserCapabilitiesResponse,
  CurrentUserResponse,
  LoginRequest,
  PasswordChangeRequest,
  TokenResponse,
} from "./authTypes";

export type {
  AdminCurrentUserCapabilitiesData,
  AdminCurrentUserCapabilitiesResponse,
  CurrentUserData,
  CurrentUserDepartment,
  CurrentUserResponse,
  CurrentUserRole,
  LoginRequest,
  PasswordChangeRequest,
  TokenResponse,
} from "./authTypes";

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

export async function getAdminCurrentUserCapabilities(
  accessToken: string,
): Promise<AdminCurrentUserCapabilitiesResponse> {
  return requestJson<AdminCurrentUserCapabilitiesResponse>(
    "/internal/v1/admin/users/me/capabilities",
    {
      method: "GET",
    },
    accessToken,
  );
}

export async function changeCurrentUserPassword(
  payload: PasswordChangeRequest,
  accessToken: string,
): Promise<void> {
  await requestVoid(
    "/internal/v1/users/me/password",
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
    accessToken,
  );
}
