import type { ComputedRef, Ref } from "vue";

import {
  createSession,
  deleteCurrentSession,
  getAdminCurrentUserCapabilities,
  refreshSession,
  type AdminCurrentUserCapabilitiesData,
  type TokenResponse,
} from "@/api/auth";
import { ApiRequestError } from "@/api/http";

export type AdminAuthTokenState = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
};

type AuthFeedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type AuthBusyState = {
  bootstrapping: boolean;
  loggingIn: boolean;
  refreshing: boolean;
  loggingOut: boolean;
};

type LoginFormState = {
  username: string;
  password: string;
};

type UseAdminSessionOptions = {
  authTokens: Ref<AdminAuthTokenState | null>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  adminAccessGranted: Ref<boolean>;
  authBusy: AuthBusyState;
  authFeedback: Ref<AuthFeedback | null>;
  loginForm: LoginFormState;
  setupModeRequired: ComputedRef<boolean>;
  canAccessAdminPortal: () => boolean;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  onSessionAccepted: () => Promise<void>;
  onClearDomainState: () => void;
  navigateTo: (path: string, replace?: boolean) => void;
};

const AUTH_STORAGE_KEY = "little-bear.admin.auth";
const TOKEN_REFRESH_SKEW_MS = 60_000;

export function loadStoredAdminAuthTokens(): AdminAuthTokenState | null {
  try {
    const raw = window.sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw);
    if (
      typeof parsed.accessToken === "string" &&
      typeof parsed.refreshToken === "string" &&
      typeof parsed.accessTokenExpiresAt === "number"
    ) {
      return parsed;
    }
  } catch {
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }
  return null;
}

export function useAdminSession(options: UseAdminSessionOptions) {
  async function submitLogin(): Promise<void> {
    const username = options.loginForm.username.trim();
    const password = options.loginForm.password;
    if (!username || !password) {
      options.authFeedback.value = {
        tone: "error",
        message: "请输入登录名和密码。",
      };
      return;
    }

    options.authBusy.loggingIn = true;
    try {
      const tokenResponse = await createSession({
        username,
        password,
      });
      saveAuthTokens(tokenResponse);
      let userResponse;
      try {
        userResponse = await getAdminCurrentUserCapabilities(tokenResponse.access_token);
      } catch (error) {
        if (isAdminPortalForbidden(error)) {
          await rejectAdminPortalLogin(tokenResponse.access_token);
          options.loginForm.password = "";
          return;
        }
        throw error;
      }
      options.currentUser.value = userResponse.data;
      if (!options.canAccessAdminPortal()) {
        await rejectAdminPortalLogin(tokenResponse.access_token);
        options.loginForm.password = "";
        return;
      }
      options.adminAccessGranted.value = true;
      await options.onSessionAccepted();
      options.loginForm.password = "";
      options.authFeedback.value = {
        tone: "success",
        message: "登录成功。",
      };
      options.navigateTo("/admin");
    } catch (error) {
      clearAuthSession();
      options.authFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "登录失败"),
      };
    } finally {
      options.authBusy.loggingIn = false;
    }
  }

  async function restoreAuthenticatedSession(): Promise<void> {
    if (!options.authTokens.value?.accessToken || options.setupModeRequired.value) {
      options.currentUser.value = null;
      return;
    }

    try {
      const accessToken = await ensureAccessToken();
      if (!accessToken) {
        clearAuthSession();
        return;
      }
      const userResponse = await getAdminCurrentUserCapabilities(accessToken);
      options.currentUser.value = userResponse.data;
      if (!options.canAccessAdminPortal()) {
        await rejectAdminPortalLogin(accessToken);
        return;
      }
      options.adminAccessGranted.value = true;
      options.authFeedback.value = null;
      await options.onSessionAccepted();
    } catch (error) {
      if (isAdminPortalForbidden(error)) {
        const accessToken = options.authTokens.value?.accessToken;
        if (accessToken) {
          await rejectAdminPortalLogin(accessToken);
          return;
        }
      }
      clearAuthSession();
    }
  }

  async function ensureAccessToken(): Promise<string | null> {
    const tokenState = options.authTokens.value;
    if (!tokenState) {
      return null;
    }
    if (Date.now() < tokenState.accessTokenExpiresAt - TOKEN_REFRESH_SKEW_MS) {
      return tokenState.accessToken;
    }
    return refreshAccessToken();
  }

  async function refreshAccessToken(): Promise<string | null> {
    const tokenState = options.authTokens.value;
    if (!tokenState?.refreshToken) {
      return null;
    }
    options.authBusy.refreshing = true;
    try {
      const response = await refreshSession(tokenState.refreshToken);
      saveAuthTokens(response);
      return response.access_token;
    } catch {
      clearAuthSession();
      return null;
    } finally {
      options.authBusy.refreshing = false;
    }
  }

  async function logout(): Promise<void> {
    const accessToken = options.authTokens.value?.accessToken;
    options.authBusy.loggingOut = true;
    try {
      if (accessToken) {
        await deleteCurrentSession(accessToken);
      }
    } catch {
      // 本地退出必须可靠，后端吊销失败不能阻塞清理本地登录态。
    } finally {
      clearAuthSession();
      options.authBusy.loggingOut = false;
      options.authFeedback.value = {
        tone: "neutral",
        message: "已退出登录。",
      };
      options.navigateTo("/admin/login");
    }
  }

  function saveAuthTokens(response: TokenResponse): void {
    const tokenState: AdminAuthTokenState = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      accessTokenExpiresAt: Date.now() + response.expires_in * 1000,
    };
    options.authTokens.value = tokenState;
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(tokenState));
  }

  function clearAuthSession(): void {
    options.authTokens.value = null;
    options.currentUser.value = null;
    options.adminAccessGranted.value = false;
    options.onClearDomainState();
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  }

  async function rejectAdminPortalLogin(accessToken: string): Promise<void> {
    try {
      await deleteCurrentSession(accessToken);
    } catch {
      // 本地会话清理必须可靠，后端吊销失败不能阻塞拒绝管理后台登录。
    }
    clearAuthSession();
    options.authFeedback.value = {
      tone: "error",
      message: "当前账号仅具备普通用户权限，不能登录管理后台。",
    };
  }

  return {
    clearAuthSession,
    ensureAccessToken,
    logout,
    restoreAuthenticatedSession,
    submitLogin,
  };
}

function isAdminPortalForbidden(error: unknown): boolean {
  return (
    error instanceof ApiRequestError &&
    error.payload?.error_code === "AUTH_ADMIN_PORTAL_FORBIDDEN"
  );
}
