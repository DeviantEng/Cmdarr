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
        <Label htmlFor="edit-la-triage-batch">{la.triageBatchSize}</Label>
        <NumericInput
          id="edit-la-triage-batch"
          value={editForm.triage_batch_size ?? editForm.analysis_batch_size ?? 100}
          onChange={(v) => setEditForm((f) => ({ ...f, triage_batch_size: v ?? 100 }))}
          min={1}
          max={500}
          defaultValue={100}
        />
        <p className="text-xs text-muted-foreground">{la.triageBatchSizeHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-deep-batch">{la.deepBatchSize}</Label>
        <NumericInput
          id="edit-la-deep-batch"
          value={editForm.deep_batch_size ?? 15}
          onChange={(v) => setEditForm((f) => ({ ...f, deep_batch_size: v ?? 15 }))}
          min={1}
          max={200}
          defaultValue={15}
        />
        <p className="text-xs text-muted-foreground">{la.deepBatchSizeHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-triage-sample">{la.triageSampleSeconds}</Label>
        <NumericInput
          id="edit-la-triage-sample"
          value={editForm.triage_sample_seconds ?? 20}
          onChange={(v) => setEditForm((f) => ({ ...f, triage_sample_seconds: v ?? 20 }))}
          min={5}
          max={120}
          defaultValue={20}
        />
        <p className="text-xs text-muted-foreground">{la.triageSampleSecondsHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-deep-sample">{la.deepSampleSeconds}</Label>
        <NumericInput
          id="edit-la-deep-sample"
          value={editForm.deep_sample_seconds ?? 60}
          onChange={(v) => setEditForm((f) => ({ ...f, deep_sample_seconds: v ?? 60 }))}
          min={15}
          max={180}
          defaultValue={60}
        />
        <p className="text-xs text-muted-foreground">{la.deepSampleSecondsHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-la-short">{la.shortTrackSeconds}</Label>
        <NumericInput
          id="edit-la-short"
          value={editForm.short_track_seconds ?? 10}
          onChange={(v) => setEditForm((f) => ({ ...f, short_track_seconds: v ?? 10 }))}
          min={1}
          max={60}
          defaultValue={10}
        />
        <p className="text-xs text-muted-foreground">{la.shortTrackSecondsHelp}</p>
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
