import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { lb } from "../shared";
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";

export function ListenbrainzCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { formData, setFormData, handleTogglePlaylistType } = wizard;
  return (
    <>
      {/* Playlist Types */}
      <div className="space-y-2">
        <Label>{lb.playlistTypesLabel}</Label>
        <div className="space-y-2">
          {["weekly_exploration", "weekly_jams", "daily_jams"].map((type) => (
            <label key={type} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={formData.playlist_types.includes(type)}
                onChange={() => handleTogglePlaylistType(type)}
                className="rounded border-input"
              />
              <span className="text-sm">
                {type
                  .split("_")
                  .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* Retention Settings */}
      <div className="space-y-2">
        <Label>{lb.retentionHeading}</Label>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label className="text-xs">{lb.weeklyExploration}</Label>
            <NumericInput
              value={formData.weekly_exploration_keep}
              onChange={(v) =>
                setFormData((prev) => ({ ...prev, weekly_exploration_keep: v ?? 3 }))
              }
              min={1}
              max={20}
              defaultValue={3}
            />
          </div>
          <div>
            <Label className="text-xs">{lb.weeklyJams}</Label>
            <NumericInput
              value={formData.weekly_jams_keep}
              onChange={(v) => setFormData((prev) => ({ ...prev, weekly_jams_keep: v ?? 3 }))}
              min={1}
              max={20}
              defaultValue={3}
            />
          </div>
          <div>
            <Label className="text-xs">{lb.dailyJams}</Label>
            <NumericInput
              value={formData.daily_jams_keep}
              onChange={(v) => setFormData((prev) => ({ ...prev, daily_jams_keep: v ?? 3 }))}
              min={1}
              max={20}
              defaultValue={3}
            />
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{lb.retentionHelper}</p>
      </div>

      {/* Cleanup Toggle */}
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={formData.cleanup_enabled}
          onChange={(e) =>
            setFormData((prev) => ({
              ...prev,
              cleanup_enabled: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{lb.cleanupCheckbox}</span>
      </label>
    </>
  );
}
