import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const lb = commandUiCopy.listenbrainz;

export function PlaylistSyncListenbrainzSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{lb.retentionHeading}</Label>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label className="text-xs">{lb.weeklyExploration}</Label>
            <NumericInput
              value={editForm.weekly_exploration_keep ?? 2}
              onChange={(v) =>
                setEditForm((f) => ({
                  ...f,
                  weekly_exploration_keep: v ?? 2,
                }))
              }
              min={1}
              max={20}
              defaultValue={2}
            />
          </div>
          <div>
            <Label className="text-xs">{lb.weeklyJams}</Label>
            <NumericInput
              value={editForm.weekly_jams_keep ?? 2}
              onChange={(v) =>
                setEditForm((f) => ({
                  ...f,
                  weekly_jams_keep: v ?? 2,
                }))
              }
              min={1}
              max={20}
              defaultValue={2}
            />
          </div>
          <div>
            <Label className="text-xs">{lb.dailyJams}</Label>
            <NumericInput
              value={editForm.daily_jams_keep ?? 3}
              onChange={(v) =>
                setEditForm((f) => ({
                  ...f,
                  daily_jams_keep: v ?? 3,
                }))
              }
              min={1}
              max={20}
              defaultValue={3}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{lb.retentionHelper}</p>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id="edit-lb-cleanup"
          checked={editForm.cleanup_enabled ?? true}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              cleanup_enabled: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <Label htmlFor="edit-lb-cleanup" className="cursor-pointer font-normal">
          {lb.cleanupCheckbox}
        </Label>
      </div>
    </>
  );
}
