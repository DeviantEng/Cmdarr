import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";

export function MoodPlaylistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, moodsList } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>Moods (select one or more)</Label>
        <div className="max-h-[200px] overflow-y-auto rounded-md border border-input p-2">
          {moodsList.length === 0 ? (
            <p className="text-sm text-muted-foreground">Loading moods...</p>
          ) : (
            <div className="grid grid-cols-3 gap-1">
              {moodsList.map((mood) => (
                <label key={mood} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={(editForm.moods ?? []).includes(mood)}
                    onChange={() => {
                      const current = editForm.moods ?? [];
                      setEditForm((f) => ({
                        ...f,
                        moods: current.includes(mood)
                          ? current.filter((m) => m !== mood)
                          : [...current, mood],
                      }));
                    }}
                    className="rounded border-input"
                  />
                  <span className="text-sm">{mood}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.use_custom_playlist_name ?? false}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">Use custom playlist name</span>
      </label>
      {editForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>Custom playlist name</Label>
          <Input
            value={editForm.custom_playlist_name ?? ""}
            onChange={(e) =>
              setEditForm((f) => ({ ...f, custom_playlist_name: e.target.value }))
            }
            placeholder="e.g. Chill Vibes"
          />
          <p className="text-xs text-muted-foreground">
            Override auto-generated name. Shown as [Cmdarr] Mood: &lt;name&gt;.
          </p>
        </div>
      )}
      {!editForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">
          Playlist name is auto-generated from mood names (e.g. Chill · Relaxed +
          2 More).
        </p>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Max tracks</Label>
          <NumericInput
            placeholder="50"
            value={editForm.max_tracks ?? 50}
            onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
            min={1}
            max={200}
            defaultValue={50}
          />
          <p className="text-xs text-muted-foreground">Min 1, max 200</p>
        </div>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.exclude_last_run ?? true}
          onChange={(e) =>
            setEditForm((f) => ({ ...f, exclude_last_run: e.target.checked }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">
          Force fresh (exclude tracks from previous run)
        </span>
      </label>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.limit_by_year ?? false}
          onChange={(e) =>
            setEditForm((f) => ({ ...f, limit_by_year: e.target.checked }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">Limit by release year (album year)</span>
      </label>
      {editForm.limit_by_year && (
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Min year</Label>
            <NumericInput
              placeholder="e.g. 1990"
              value={editForm.min_year}
              onChange={(v) => setEditForm((f) => ({ ...f, min_year: v }))}
              min={1800}
              max={2100}
              allowEmpty
            />
          </div>
          <div className="space-y-2">
            <Label>Max year</Label>
            <NumericInput
              placeholder="e.g. 2010"
              value={editForm.max_year}
              onChange={(v) => setEditForm((f) => ({ ...f, max_year: v }))}
              min={1800}
              max={2100}
              allowEmpty
            />
          </div>
        </div>
      )}
      {editForm.limit_by_year && (
        <p className="text-xs text-muted-foreground">
          Set min and/or max. Tracks without year metadata are excluded. Range:
          1800–2100.
        </p>
      )}
  </>
    );
}
