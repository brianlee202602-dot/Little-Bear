export type ApiError = {
  request_id: string;
  error_code: string;
  message: string;
  stage: string;
  retryable: boolean;
  details: Record<string, unknown>;
};
