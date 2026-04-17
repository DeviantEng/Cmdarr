import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const ae = commandUiCopy.artistEvents;

export function ArtistEventsRefreshSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-ae-artists">{ae.artistsPerRun}</Label>
        <NumericInput
          id="edit-ae-artists"
          value={editForm.artists_per_run ?? 20}
          onChange={(v) => setEditForm((f) => ({ ...f, artists_per_run: v ?? 20 }))}
          min={1}
          max={50}
          defaultValue={20}
        />
        <p className="text-xs text-muted-foreground">{ae.artistsPerRunHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-ae-ttl">{ae.refreshTtl}</Label>
        <NumericInput
          id="edit-ae-ttl"
          value={editForm.refresh_ttl_days ?? 14}
          onChange={(v) => setEditForm((f) => ({ ...f, refresh_ttl_days: v ?? 14 }))}
          min={1}
          max={365}
          defaultValue={14}
        />
        <p className="text-xs text-muted-foreground">{ae.refreshTtlHelp}</p>
      </div>
    </>
  );
}
