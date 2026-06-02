import type { SetupFormModel } from "@/features/setup/setupModel";
import {
  accessSection,
  adminSection,
  infraSection,
  organizationSection,
} from "@/features/setup/setupBasicFieldSections";
import {
  cacheSection,
  chunkSection,
  modelSection,
} from "@/features/setup/setupModelFieldSections";
import {
  advancedConfigSection,
  policySection,
} from "@/features/setup/setupPolicyFieldSections";
import type { FieldDefinition } from "@/features/setup/setupFieldTypes";

export type {
  FieldDefinition,
  FieldInput,
  FieldOption,
  FieldSection,
} from "@/features/setup/setupFieldTypes";
export {
  accessSection,
  adminSection,
  infraSection,
  organizationSection,
} from "@/features/setup/setupBasicFieldSections";
export {
  cacheSection,
  chunkSection,
  modelSection,
} from "@/features/setup/setupModelFieldSections";
export {
  advancedConfigSection,
  policySection,
} from "@/features/setup/setupPolicyFieldSections";

// 以下 FieldSection 是“表单元数据”：模板按定义渲染字段，减少重复 DOM 和字段遗漏。
export const sections = [
  accessSection,
  adminSection,
  organizationSection,
  infraSection,
  modelSection,
  chunkSection,
  policySection,
  cacheSection,
];

export const allConfigFieldSections = [...sections, advancedConfigSection];

export const setupFieldByKey = new Map<keyof SetupFormModel, FieldDefinition>(
  allConfigFieldSections.flatMap((section) =>
    section.fields.map((field) => [field.key, field] as const),
  ),
);

export function setupFields(...keys: Array<keyof SetupFormModel>): FieldDefinition[] {
  return keys
    .map((key) => setupFieldByKey.get(key))
    .filter((field): field is FieldDefinition => Boolean(field));
}
