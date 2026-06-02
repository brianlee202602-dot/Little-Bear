export type SetupTone = "success" | "error" | "warning" | "neutral";

export type SetupBusyState = {
  refreshing: boolean;
  validating: boolean;
  submitting: boolean;
};

export type SetupFeedback = {
  tone: "success" | "error" | "neutral";
  message: string;
};
