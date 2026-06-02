import { computed, onMounted, reactive, ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type { AdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import type { AdminNavigationProvider } from "@/app/providers/adminNavigationProvider";
import type { AdminSessionProvider } from "@/app/providers/adminSessionProvider";
import { useAdminBootstrap } from "@/app/useAdminBootstrap";
import { useAdminNavigation } from "@/app/useAdminNavigation";
import {
  loadStoredAdminAuthTokens,
  useAdminSession,
  type AdminAuthTokenState,
} from "@/app/useAdminSession";
import { useAdminCapabilities } from "@/composables/useAdminCapabilities";
import { useSetupFlow } from "@/features/setup/useSetupFlow";
import { formatRoleList } from "@/utils/roles";
import { normalizeErrorMessage } from "@/utils/errors";
import type { Tone } from "@/utils/status";

export function useAdminAppRuntime() {
  const authBusy = reactive({
    bootstrapping: true,
    loggingIn: false,
    refreshing: false,
    loggingOut: false,
  });
  const loginForm = reactive({
    username: "",
    password: "",
  });
  const authFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
  const authTokens = ref<AdminAuthTokenState | null>(loadStoredAdminAuthTokens());
  const currentUser = ref<AdminCurrentUserCapabilitiesData | null>(null);
  const adminAccessGranted = ref(false);

  const setupFlow = useSetupFlow({
    normalizeErrorMessage,
  });
  const authenticated = computed(() => Boolean(authTokens.value?.accessToken && currentUser.value));
  const userDisplayName = computed(() => currentUser.value?.name || currentUser.value?.username || "-");
  const userRoleLabels = computed(() => formatRoleList(currentUser.value?.roles ?? []));
  const adminCapabilityProvider = useAdminCapabilities(currentUser);
  const { canAccessAdminPortal, canAccessAdminTab, visibleAdminTabs } = adminCapabilityProvider;
  const adminNavigationProvider = useAdminNavigation({
    canAccessAdminTab,
    closeTabTransientPanels: () => undefined,
    refreshSelectedAdminTabState,
    visibleAdminTabs,
  });
  const {
    ensureVisibleAdminTab,
    navigateTo,
    selectedAdminTab,
    switchAdminTab,
  } = adminNavigationProvider;
  const {
    activeView,
    refreshState,
    setupModeRequired,
    syncRouteToCurrentState,
  } = useAdminBootstrap({
    adminAccessGranted,
    authenticated,
    authBusy,
    busy: setupFlow.busy,
    feedback: setupFlow.feedback,
    navigateTo,
    normalizeErrorMessage,
    setupState: setupFlow.setupState,
    setupToken: computed(() => setupFlow.form.setupToken),
  });
  setupFlow.setRefreshStateHandler(refreshState);
  const {
    ensureAccessToken,
    logout,
    restoreAuthenticatedSession,
    submitLogin,
  } = useAdminSession({
    adminAccessGranted,
    authBusy,
    authFeedback,
    authTokens,
    canAccessAdminPortal,
    currentUser,
    loginForm,
    navigateTo,
    normalizeErrorMessage,
    onClearDomainState: clearAdminDomainState,
    onSessionAccepted: async () => {
      ensureVisibleAdminTab();
      await refreshSelectedAdminTabState();
    },
    setupModeRequired,
  });

  onMounted(async () => {
    authBusy.bootstrapping = true;
    try {
      await refreshState();
      await restoreAuthenticatedSession();
      syncRouteToCurrentState();
    } finally {
      authBusy.bootstrapping = false;
    }
  });

  async function refreshSelectedAdminTabState(): Promise<void> {
    if (!canAccessAdminTab(selectedAdminTab.value)) {
      return;
    }
  }

  function clearAdminDomainState(): void {
    return undefined;
  }

  const adminSessionProvider: AdminSessionProvider = {
    authenticated,
    authBusy,
    authFeedback,
    currentUser,
    ensureAccessToken,
    logout,
    userDisplayName,
    userRoleLabels,
  };
  const adminNavigationProviderState: AdminNavigationProvider = {
    canAccessAdminTab,
    ensureVisibleAdminTab,
    navigateTo,
    selectedAdminTab,
    switchAdminTab,
    visibleAdminTabs,
  };

  return {
    activeView,
    adminCapabilityProvider: adminCapabilityProvider as AdminCapabilityProvider,
    adminNavigationProvider: adminNavigationProviderState,
    adminSessionProvider,
    authBusy,
    authFeedback,
    canAccessAdminTab,
    loginForm,
    logout,
    selectedAdminTab,
    setupFlow,
    submitLogin,
    switchAdminTab,
    userDisplayName,
    userRoleLabels,
    visibleAdminTabs,
  };
}

export type AdminAppRuntime = ReturnType<typeof useAdminAppRuntime>;
