export interface SetupStateData {
  initialized: boolean;
  setup_status: string;
  active_config_version: number | null;
  setup_required: boolean;
  active_config_present: boolean;
  recovery_setup_allowed: boolean;
  recovery_reason: string | null;
  setup_token_expires_at: string | null;
  error_code: string | null;
  error_message: string | null;
}

export interface SetupStateResponse {
  request_id: string;
  data: SetupStateData;
}

export interface SetupIssue {
  code?: string;
  error_code?: string;
  path?: string;
  message?: string;
  retryable?: boolean;
  [key: string]: unknown;
}

export interface SetupValidationData {
  valid: boolean;
  errors: SetupIssue[];
  warnings: SetupIssue[];
}

export interface SetupValidationResponse {
  request_id: string;
  data: SetupValidationData;
}

export interface SetupInitializationData {
  initialized: boolean;
  active_config_version: number;
  enterprise_id: string;
  admin_user_id: string;
}

export interface SetupInitializationResponse {
  request_id: string;
  data: SetupInitializationData;
}
