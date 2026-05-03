export const HEALTH_ENDPOINTS = {
  live: "/health/live",
  ready: "/health/ready",
} as const;

export const INTERNAL_ENDPOINTS = {
  queries: "/internal/v1/queries",
  queryStreams: "/internal/v1/query-streams",
} as const;
