import type { Ref } from "vue";

import type { FieldDefinition } from "@/features/setup/setupFields";
import type { SetupFormModel } from "@/features/setup/setupModel";

type StringFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends string ? K : never;
}[keyof SetupFormModel];
type NumberFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends number ? K : never;
}[keyof SetupFormModel];
type BooleanFieldKey = {
  [K in keyof SetupFormModel]: SetupFormModel[K] extends boolean ? K : never;
}[keyof SetupFormModel];

export function useSetupFieldUpdates(form: SetupFormModel, submitConfirmed: Ref<boolean>) {
  function updateStringField(key: StringFieldKey, value: string): void {
    (form as unknown as Record<string, string>)[key] = value;
  }

  function updateNumberField(key: NumberFieldKey, value: string): void {
    const parsed = Number(value);
    (form as unknown as Record<string, number>)[key] = Number.isFinite(parsed) ? parsed : 0;
  }

  function updateBooleanField(key: BooleanFieldKey, value: boolean): void {
    (form as unknown as Record<string, boolean>)[key] = value;
  }

  function updateFieldFromInput(field: FieldDefinition, value: string): void {
    if (field.input === "number") {
      updateNumberField(field.key as NumberFieldKey, value);
      return;
    }
    updateStringField(field.key as StringFieldKey, value);
  }

  function updateFieldFromSelect(field: FieldDefinition, value: string): void {
    updateStringField(field.key as StringFieldKey, value);
  }

  function updateFieldFromCheckbox(field: FieldDefinition, value: boolean): void {
    updateBooleanField(field.key as BooleanFieldKey, value);
  }

  function updateSubmitConfirmed(value: boolean): void {
    submitConfirmed.value = value;
  }

  return {
    updateFieldFromCheckbox,
    updateFieldFromInput,
    updateFieldFromSelect,
    updateSubmitConfirmed,
  };
}
