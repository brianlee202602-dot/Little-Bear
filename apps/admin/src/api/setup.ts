import { requestJson } from "./http";
import type {
  SetupInitializationResponse,
  SetupStateResponse,
  SetupValidationResponse,
} from "./setupTypes";

export type {
  SetupInitializationData,
  SetupInitializationResponse,
  SetupIssue,
  SetupStateData,
  SetupStateResponse,
  SetupValidationData,
  SetupValidationResponse,
} from "./setupTypes";

export async function getSetupState(setupToken?: string): Promise<SetupStateResponse> {
  return requestJson<SetupStateResponse>("/internal/v1/setup-state", { method: "GET" }, setupToken);
}

export async function validateSetupConfig(
  payload: unknown,
  setupToken?: string,
): Promise<SetupValidationResponse> {
  return requestJson<SetupValidationResponse>(
    "/internal/v1/setup-config-validations",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    setupToken,
  );
}

export async function initializeSetup(
  payload: unknown,
  setupToken?: string,
): Promise<SetupInitializationResponse> {
  return requestJson<SetupInitializationResponse>(
    "/internal/v1/setup-initialization",
    {
      method: "PUT",
      body: JSON.stringify(payload),
      headers: {
        "x-setup-confirm": "initialize",
      },
    },
    setupToken,
  );
}
