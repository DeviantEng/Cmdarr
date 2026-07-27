import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { commandUiCopy } from "@/command-spec";

const lm = commandUiCopy.lidarrMaintenance;

export function LidarrWantedSearchSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-lidarr-ws-topx">{lm.topXLabel}</Label>
        <NumericInput
          id="edit-lidarr-ws-topx"
          value={editForm.top_x ?? 10}
          onChange={(v) => setEditForm((f) => ({ ...f, top_x: v ?? 10 }))}
          min={1}
          max={50}
          defaultValue={10}
        />
        <p className="text-xs text-muted-foreground">{lm.topXHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-lidarr-ws-ignore">{lm.ignoreDaysLabel}</Label>
        <NumericInput
          id="edit-lidarr-ws-ignore"
          value={editForm.ignore_days ?? 14}
          onChange={(v) => setEditForm((f) => ({ ...f, ignore_days: v ?? 14 }))}
          min={1}
          max={365}
          defaultValue={14}
        />
        <p className="text-xs text-muted-foreground">{lm.ignoreDaysHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-lidarr-ws-sort">{lm.sortByLabel}</Label>
        <Select
          value={editForm.sort_by ?? "oldest_release_date"}
          onValueChange={(v) => setEditForm((f) => ({ ...f, sort_by: v }))}
        >
          <SelectTrigger id="edit-lidarr-ws-sort">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="oldest_release_date">{lm.sortOldest}</SelectItem>
            <SelectItem value="newest_release_date">{lm.sortNewest}</SelectItem>
            <SelectItem value="artist_name_asc">{lm.sortArtist}</SelectItem>
            <SelectItem value="album_title_asc">{lm.sortTitle}</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{lm.sortByHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{lm.releaseTypesHeading}</Label>
        <div className="flex flex-wrap gap-4">
          {["album", "ep", "single", "other"].map((t) => (
            <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={(editForm.album_types ?? ["album"]).includes(t)}
                onChange={(e) => {
                  setEditForm((f) => {
                    const current = f.album_types ?? ["album"];
                    const next = e.target.checked
                      ? [...current, t]
                      : current.filter((x) => x !== t);
                    return { ...f, album_types: next.length ? next : ["album"] };
                  });
                }}
                className="rounded border-input"
              />
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{lm.releaseTypesHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-lidarr-ws-settle">{lm.settleSecondsLabel}</Label>
        <NumericInput
          id="edit-lidarr-ws-settle"
          value={editForm.settle_seconds ?? 15}
          onChange={(v) => setEditForm((f) => ({ ...f, settle_seconds: v ?? 15 }))}
          min={0}
          max={300}
          defaultValue={15}
        />
        <p className="text-xs text-muted-foreground">{lm.settleSecondsHelp}</p>
      </div>
    </>
  );
}
