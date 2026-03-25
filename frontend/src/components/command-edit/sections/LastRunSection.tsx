import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { commandUiCopy } from "@/command-spec";

export function LastRunSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand } = ctx;
  return (
    <>
  {editingCommand.last_run && (
    <div className="space-y-2">
      <Label>{commandUiCopy.lastRun.label}</Label>
      <Input
        value={new Date(editingCommand.last_run).toLocaleString()}
        disabled
      />
    </div>
  )}
  </>
    );
}
