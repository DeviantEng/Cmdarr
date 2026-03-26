import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const m = commandUiCopy.moodPlaylist;

export function MoodPlaylistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, moodsList } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{m.moodsHeading}</Label>
        <div className="max-h-[200px] overflow-y-auto rounded-md border border-input p-2">
          {moodsList.length === 0 ? (
            <p className="text-sm text-muted-foreground">{m.loadingMoods}</p>
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
                          ? current.filter((x) => x !== mood)
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
        <span className="text-sm">{m.useCustomPlaylistName}</span>
      </label>
      {editForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{m.customPlaylistNameLabel}</Label>
          <Input
            value={editForm.custom_playlist_name ?? ""}
            onChange={(e) => setEditForm((f) => ({ ...f, custom_playlist_name: e.target.value }))}
            placeholder={m.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{m.customPlaylistNameHelper}</p>
        </div>
      )}
      {!editForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{m.autoNameHelp}</p>
      )}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{m.maxTracksLabel}</Label>
          <NumericInput
            placeholder="50"
            value={editForm.max_tracks ?? 50}
            onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
            min={1}
            max={200}
            defaultValue={50}
          />
          <p className="text-xs text-muted-foreground">{m.maxTracksHelp}</p>
        </div>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.exclude_last_run ?? true}
          onChange={(e) => setEditForm((f) => ({ ...f, exclude_last_run: e.target.checked }))}
          className="rounded border-input"
        />
        <span className="text-sm">{m.forceFresh}</span>
      </label>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.limit_by_year ?? false}
          onChange={(e) => setEditForm((f) => ({ ...f, limit_by_year: e.target.checked }))}
          className="rounded border-input"
        />
        <span className="text-sm">{m.limitByYear}</span>
      </label>
      {editForm.limit_by_year && (
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{m.minYear}</Label>
            <NumericInput
              placeholder={m.minYearPlaceholder}
              value={editForm.min_year}
              onChange={(v) => setEditForm((f) => ({ ...f, min_year: v }))}
              min={1800}
              max={2100}
              allowEmpty
            />
          </div>
          <div className="space-y-2">
            <Label>{m.maxYear}</Label>
            <NumericInput
              placeholder={m.maxYearPlaceholder}
              value={editForm.max_year}
              onChange={(v) => setEditForm((f) => ({ ...f, max_year: v }))}
              min={1800}
              max={2100}
              allowEmpty
            />
          </div>
        </div>
      )}
      {editForm.limit_by_year && <p className="text-xs text-muted-foreground">{m.yearRangeHelp}</p>}
    </>
  );
}
