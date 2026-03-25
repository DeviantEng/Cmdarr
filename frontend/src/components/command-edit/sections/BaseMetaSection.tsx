import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { commandUiCopy } from "@/command-spec";

export function BaseMetaSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{commandUiCopy.base.displayNameLabel}</Label>
        <Input value={editingCommand.display_name} disabled />
      </div>
      <div className="space-y-2">
        <Label>{commandUiCopy.base.descriptionLabel}</Label>
        <Input value={String(editingCommand.description ?? "")} disabled />
      </div>
    </>
  );
}
