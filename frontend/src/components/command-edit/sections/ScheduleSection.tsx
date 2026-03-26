import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { commandUiCopy } from "@/command-spec";

export function ScheduleSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand, editForm, setEditForm } = ctx;
  return (
    <>
      {!editingCommand.command_name.startsWith("daylist_") && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="edit-schedule-override"
              checked={editForm.schedule_override ?? false}
              onChange={(e) => setEditForm((f) => ({ ...f, schedule_override: e.target.checked }))}
              className="rounded border-input"
            />
            <Label htmlFor="edit-schedule-override">{commandUiCopy.schedule.overrideLabel}</Label>
          </div>
          {editForm.schedule_override && (
            <>
              <div className="space-y-2 rounded-lg border p-4">
                <Input
                  id="edit-schedule-cron"
                  placeholder={commandUiCopy.schedule.cronPlaceholder}
                  value={editForm.schedule_cron ?? "0 3 * * *"}
                  onChange={(e) => setEditForm((f) => ({ ...f, schedule_cron: e.target.value }))}
                />
              </div>
              <p className="text-xs text-muted-foreground">{commandUiCopy.schedule.cronHelp}</p>
            </>
          )}
          {!editForm.schedule_override && (
            <p className="text-xs text-muted-foreground">
              {commandUiCopy.schedule.usesGlobalDefault}
            </p>
          )}
        </div>
      )}
    </>
  );
}
