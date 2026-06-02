import { computed, reactive, ref } from "vue";

import {
  createSession,
  deleteCurrentSession,
  getCurrentUser,
  refreshSession,
  type CurrentUserData,
  type TokenResponse,
} from "@/api/auth";
import {
  readJsonFromStorage,
  removeStorageItem,
  writeJsonToStorage,
} from "@/utils/storage";

const AUTH_STORAGE_KEY = "little-bear.web.auth";
const TOKEN_REFRESH_SKEW_MS = 60_000;

type AuthTokenState = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
};

type UseAuthSessionOptions = {
  formatError: (error: unknown) => string;
  onSessionCleared?: () => void;
};

export function useAuthSession(options: UseAuthSessionOptions) {
  const authTokens = ref<AuthTokenState | null>(loadStoredAuthTokens());
  const currentUser = ref<CurrentUserData | null>(null);
  const feedback = ref("");
  const busy = reactive({
    restoring: true,
    loggingIn: false,
    refreshing: false,
    loggingOut: false,
  });
  const authenticated = computed(() => Boolean(currentUser.value && authTokens.value?.accessToken));

  async function login(usernameValue: string, passwordValue: string): Promise<string | null> {
    const username = usernameValue.trim();
    if (!username || !passwordValue) {
      feedback.value = "请输入用户名和密码。";
      return null;
    }
    busy.loggingIn = true;
    feedback.value = "";
    try {
      const tokenResponse = await createSession({
        username,
        password: passwordValue,
      });
      saveAuthTokens(tokenResponse);
      const userResponse = await getCurrentUser(tokenResponse.access_token);
      currentUser.value = userResponse.data;
      return tokenResponse.access_token;
    } catch (error) {
      clearAuthSession();
      feedback.value = options.formatError(error);
      return null;
    } finally {
      busy.loggingIn = false;
    }
  }

  async function restore(): Promise<string | null> {
    busy.restoring = true;
    try {
      const accessToken = await ensureAccessToken();
      if (!accessToken) {
        clearAuthSession();
        return null;
      }
      const userResponse = await getCurrentUser(accessToken);
      currentUser.value = userResponse.data;
      return accessToken;
    } catch {
      clearAuthSession();
      return null;
    } finally {
      busy.restoring = false;
    }
  }

  async function ensureAccessToken(): Promise<string | null> {
    const tokenState = authTokens.value;
    if (!tokenState) {
      return null;
    }
    if (Date.now() < tokenState.accessTokenExpiresAt - TOKEN_REFRESH_SKEW_MS) {
      return tokenState.accessToken;
    }
    return refreshAccessToken();
  }

  async function refreshAccessToken(): Promise<string | null> {
    const tokenState = authTokens.value;
    if (!tokenState?.refreshToken) {
      return null;
    }
    busy.refreshing = true;
    try {
      const response = await refreshSession(tokenState.refreshToken);
      saveAuthTokens(response);
      return response.access_token;
    } catch {
      clearAuthSession();
      return null;
    } finally {
      busy.refreshing = false;
    }
  }

  async function logout(): Promise<void> {
    const accessToken = authTokens.value?.accessToken;
    busy.loggingOut = true;
    try {
      if (accessToken) {
        await deleteCurrentSession(accessToken);
      }
    } catch {
      // 本地退出必须可靠，后端吊销失败不能阻塞清理页面登录态。
    } finally {
      clearAuthSession();
      busy.loggingOut = false;
    }
  }

  function clearAuthSession(): void {
    authTokens.value = null;
    currentUser.value = null;
    feedback.value = "";
    removeStorageItem(AUTH_STORAGE_KEY, "session");
    options.onSessionCleared?.();
  }

  function saveAuthTokens(response: TokenResponse): void {
    const tokenState: AuthTokenState = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      accessTokenExpiresAt: Date.now() + response.expires_in * 1000,
    };
    authTokens.value = tokenState;
    writeJsonToStorage(AUTH_STORAGE_KEY, tokenState, "session");
  }

  return {
    authenticated,
    busy,
    currentUser,
    feedback,
    clearAuthSession,
    ensureAccessToken,
    login,
    logout,
    restore,
  };
}

function loadStoredAuthTokens(): AuthTokenState | null {
  const parsed = readJsonFromStorage<Partial<AuthTokenState>>(AUTH_STORAGE_KEY, "session");
  if (
    parsed &&
    typeof parsed.accessToken === "string" &&
    typeof parsed.refreshToken === "string" &&
    typeof parsed.accessTokenExpiresAt === "number"
  ) {
    return {
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken,
      accessTokenExpiresAt: parsed.accessTokenExpiresAt,
    };
  }
  return null;
}
