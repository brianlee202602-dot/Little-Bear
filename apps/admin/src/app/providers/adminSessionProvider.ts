import { inject, provide, type ComputedRef, type InjectionKey, type Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";

export type AdminAuthBusyState = {
  bootstrapping: boolean;
  loggingIn: boolean;
  refreshing: boolean;
  loggingOut: boolean;
};

export type AdminAuthFeedback = {
  tone: "neutral" | "error" | "success";
  message: string;
};

export interface AdminSessionProvider {
  authenticated: ComputedRef<boolean>;
  authBusy: AdminAuthBusyState;
  authFeedback: Ref<AdminAuthFeedback | null>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  ensureAccessToken: () => Promise<string | null>;
  logout: () => Promise<void>;
  userDisplayName: ComputedRef<string>;
  userRoleLabels: ComputedRef<string>;
}

const ADMIN_SESSION_PROVIDER_KEY: InjectionKey<AdminSessionProvider> =
  Symbol("AdminSessionProvider");

export function provideAdminSession(provider: AdminSessionProvider): void {
  provide(ADMIN_SESSION_PROVIDER_KEY, provider);
}

export function useAdminSessionProvider(): AdminSessionProvider {
  const provider = inject(ADMIN_SESSION_PROVIDER_KEY);
  if (!provider) {
    throw new Error("ADMIN_SESSION_PROVIDER_MISSING");
  }
  return provider;
}
