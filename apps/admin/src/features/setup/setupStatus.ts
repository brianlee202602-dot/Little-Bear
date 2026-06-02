import type { SetupTone } from "@/features/setup/setupFlowTypes";

export const setupStatusLabels: Record<string, string> = {
  not_initialized: "未初始化",
  setup_required: "等待初始化",
  validating_config: "校验中",
  testing_dependencies: "依赖测试中",
  creating_admin: "创建管理员中",
  publishing_config: "发布配置中",
  initialized: "已初始化",
  validation_failed: "校验失败",
  dependency_test_failed: "依赖测试失败",
  initialization_failed: "初始化失败",
  recovery_required: "需要恢复初始化",
  recovery_validating_config: "恢复校验中",
  recovery_publishing_config: "恢复发布中",
};

export function formatSetupStatus(status: string): string {
  return setupStatusLabels[status] ?? status;
}

export function setupStateTone(
  state: { initialized: boolean; error_code?: string | null; setup_status: string } | null,
): SetupTone {
  if (!state) {
    return "neutral";
  }
  if (state.initialized) {
    return "success";
  }
  if (state.error_code || state.setup_status.includes("failed")) {
    return "error";
  }
  return "warning";
}
