import type { SetupFormModel } from "@/features/setup/setupModel";

export type FieldInput = "text" | "email" | "password" | "number" | "select" | "checkbox";

export type FieldOption = {
  label: string;
  value: string;
};

export type FieldDefinition = {
  key: keyof SetupFormModel;
  label: string;
  input: FieldInput;
  placeholder?: string;
  hint?: string;
  min?: number;
  step?: number;
  span?: "full" | "half";
  group?: string;
  options?: FieldOption[];
  required?: boolean;
};

export type FieldSection = {
  title: string;
  fields: FieldDefinition[];
};
