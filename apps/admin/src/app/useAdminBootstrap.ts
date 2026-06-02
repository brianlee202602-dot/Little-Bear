import { computed, type ComputedRef, type Ref } from "vue";

import { getSetupState, type SetupStateData } from "@/api/setup";

export type AdminActiveView = "loading" | "setup" | "login" | "dashboard";

type SetupFeedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};

type UseAdminBootstrapOptions = {
  setupState: Ref<SetupStateData | null>;
  busy: {
    refreshing: boolean;
  };
  authBusy: {
    bootstrapping: boolean;
  };
  feedback: Ref<SetupFeedback | null>;
  setupToken: ComputedRef<string>;
  authenticated: ComputedRef<boolean>;
  adminAccessGranted: Ref<boolean>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  navigateTo: (path: string, replace?: boolean) => void;
};

export function useAdminBootstrap(options: UseAdminBootstrapOptions) {
  const setupModeRequired = computed(() => {
    if (!options.setupState.value) {
      return false;
    }
    return (
      options.setupState.value.initialized !== true ||
      options.setupState.value.recovery_setup_allowed === true
    );
  });

  const activeView = computed<AdminActiveView>(() => {
    if (options.authBusy.bootstrapping || !options.setupState.value) {
      return "loading";
    }
    if (setupModeRequired.value) {
      return "setup";
    }
    if (!options.authenticated.value) {
      return "login";
    }
    if (!options.adminAccessGranted.value) {
      return "login";
    }
    return "dashboard";
  });

  async function refreshState(): Promise<void> {
    options.busy.refreshing = true;
    try {
      // setup-state 不依赖初始化令牌；传入 token 只是为了复用统一的请求客户端。
      const token = options.setupToken.value.trim() || undefined;
      const response = await getSetupState(token);
      options.setupState.value = response.data;
      options.feedback.value = null;
      if (!options.authBusy.bootstrapping) {
        syncRouteToCurrentState();
      }
    } catch (error) {
      options.feedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取 setup 状态失败"),
      };
    } finally {
      options.busy.refreshing = false;
    }
  }

  function syncRouteToCurrentState(): void {
    const path = window.location.pathname;
    if (!options.setupState.value) {
      return;
    }
    if (setupModeRequired.value) {
      if (path !== "/admin/setup-initialization") {
        options.navigateTo("/admin/setup-initialization", true);
      }
      return;
    }
    if (path === "/admin/setup-initialization") {
      options.navigateTo(options.authenticated.value ? "/admin" : "/admin/login", true);
      return;
    }
    if (options.authenticated.value && path === "/admin/login") {
      options.navigateTo("/admin", true);
      return;
    }
    if ((path === "/admin" || path === "/admin/") && !options.authenticated.value) {
      options.navigateTo("/admin/login", true);
    }
  }

  return {
    activeView,
    refreshState,
    setupModeRequired,
    syncRouteToCurrentState,
  };
}
