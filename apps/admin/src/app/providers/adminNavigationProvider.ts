import { inject, provide, type ComputedRef, type InjectionKey, type Ref } from "vue";

import type { ActiveAdminTab, AdminTabDefinition } from "@/app/navigation";

export interface AdminNavigationProvider {
  canAccessAdminTab: (tab: ActiveAdminTab) => boolean;
  ensureVisibleAdminTab: () => void;
  navigateTo: (path: string, replace?: boolean) => void;
  selectedAdminTab: Ref<ActiveAdminTab>;
  switchAdminTab: (tab: ActiveAdminTab) => void;
  visibleAdminTabs: ComputedRef<AdminTabDefinition[]>;
}

const ADMIN_NAVIGATION_PROVIDER_KEY: InjectionKey<AdminNavigationProvider> =
  Symbol("AdminNavigationProvider");

export function provideAdminNavigation(provider: AdminNavigationProvider): void {
  provide(ADMIN_NAVIGATION_PROVIDER_KEY, provider);
}

export function useAdminNavigationProvider(): AdminNavigationProvider {
  const provider = inject(ADMIN_NAVIGATION_PROVIDER_KEY);
  if (!provider) {
    throw new Error("ADMIN_NAVIGATION_PROVIDER_MISSING");
  }
  return provider;
}
