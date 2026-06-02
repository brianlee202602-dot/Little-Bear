import { ref, type ComputedRef } from "vue";

import type { ActiveAdminTab, AdminTabDefinition } from "@/app/navigation";

type UseAdminNavigationOptions = {
  canAccessAdminTab: (tab: ActiveAdminTab) => boolean;
  visibleAdminTabs: ComputedRef<AdminTabDefinition[]>;
  closeTabTransientPanels: (tab: ActiveAdminTab) => void;
  refreshSelectedAdminTabState: () => Promise<void>;
};

export function useAdminNavigation(options: UseAdminNavigationOptions) {
  const selectedAdminTab = ref<ActiveAdminTab>("config");

  function ensureVisibleAdminTab(): void {
    if (options.canAccessAdminTab(selectedAdminTab.value)) {
      return;
    }
    selectedAdminTab.value = options.visibleAdminTabs.value[0]?.key ?? "config";
  }

  function switchAdminTab(tab: ActiveAdminTab): void {
    if (!options.canAccessAdminTab(tab)) {
      ensureVisibleAdminTab();
      return;
    }
    selectedAdminTab.value = tab;
    options.closeTabTransientPanels(tab);
    void options.refreshSelectedAdminTabState();
  }

  function navigateTo(path: string, replace = false): void {
    if (window.location.pathname === path) {
      return;
    }
    if (replace) {
      window.history.replaceState(null, "", path);
      return;
    }
    window.history.pushState(null, "", path);
  }

  return {
    ensureVisibleAdminTab,
    navigateTo,
    selectedAdminTab,
    switchAdminTab,
  };
}
