import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { commandUiCopy } from "@/command-spec";

export function LastStatusSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand } = ctx;
  return (
    <>
  {editingCommand.last_success !== null && (
    <div className="space-y-2">
      <Label>{commandUiCopy.lastStatus.label}</Label>
      <Badge variant={editingCommand.last_success ? "default" : "destructive"}>
        {editingCommand.last_success
          ? commandUiCopy.lastStatus.success
          : commandUiCopy.lastStatus.failed}
      </Badge>
    </div>
  )}
  </>
    );
}
