import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const la = commandUiCopy.libraryAudit;

export function LibraryAuditSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-la-batch">{la.batchSize}</Label>
        <NumericInput
          id="edit-la-batch"
          value={editForm.analysis_batch_size ?? 25}
          onChange={(v) => setEditForm((f) => ({ ...f, analysis_batch_size: v ?? 25 }))}
          min={1}
          max={500}
          defaultValue={25}
        />
        <p className="text-xs text-muted-foreground">{la.batchSizeHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-inv">{la.inventoryInterval}</Label>
        <NumericInput
          id="edit-la-inv"
          value={editForm.inventory_interval_hours ?? 24}
          onChange={(v) => setEditForm((f) => ({ ...f, inventory_interval_hours: v ?? 24 }))}
          min={1}
          max={168}
          defaultValue={24}
        />
        <p className="text-xs text-muted-foreground">{la.inventoryIntervalHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-ret">{la.missingRetention}</Label>
        <NumericInput
          id="edit-la-ret"
          value={editForm.missing_retention_days ?? 90}
          onChange={(v) => setEditForm((f) => ({ ...f, missing_retention_days: v ?? 90 }))}
          min={1}
          max={3650}
          defaultValue={90}
        />
        <p className="text-xs text-muted-foreground">{la.missingRetentionHelp}</p>
      </div>
    </>
  );
}
