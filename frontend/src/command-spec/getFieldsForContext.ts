import { COMPOUND_FIELDS } from "./fields/compoundFields";
import type { CompoundFieldDef, ResolveContext } from "./uiTypes";

/** Returns compound field definitions that apply to this context, in stable order. */
export function getFieldsForContext(ctx: ResolveContext): CompoundFieldDef[] {
  return COMPOUND_FIELDS.filter((f) => f.visible(ctx));
}

export function isCompoundFieldVisible(fieldId: string, ctx: ResolveContext): boolean {
  const f = COMPOUND_FIELDS.find((x) => x.id === fieldId);
  return f ? f.visible(ctx) : false;
}

export function isCompoundFieldEditable(fieldId: string, ctx: ResolveContext): boolean {
  const f = COMPOUND_FIELDS.find((x) => x.id === fieldId);
  return f ? f.editable(ctx) : false;
}
