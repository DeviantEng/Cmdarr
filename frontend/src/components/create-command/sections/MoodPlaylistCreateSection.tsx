import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { mood } from "../shared";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";

export function MoodPlaylistCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { moodPlaylistForm, setMoodPlaylistForm, moodsList, handleToggleMood } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{mood.moodsHeading}</Label>
        <div className="max-h-[200px] overflow-y-auto rounded-md border border-input p-2">
          {moodsList.length === 0 ? (
            <p className="text-sm text-muted-foreground">{mood.loadingMoods}</p>
          ) : (
            <div className="grid grid-cols-3 gap-1">
              {moodsList.map((moodName) => (
                <label key={moodName} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={moodPlaylistForm.moods.includes(moodName)}
                    onChange={() => handleToggleMood(moodName)}
                    className="rounded border-input"
                  />
                  <span className="text-sm">{moodName}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{mood.rankingHelper}</p>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={moodPlaylistForm.use_custom_playlist_name}
          onChange={(e) =>
            setMoodPlaylistForm((prev) => ({
              ...prev,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{mood.useCustomPlaylistName}</span>
      </label>
      {moodPlaylistForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{mood.customPlaylistNameLabel}</Label>
          <Input
            value={moodPlaylistForm.custom_playlist_name}
            onChange={(e) =>
              setMoodPlaylistForm((prev) => ({
                ...prev,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={mood.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{mood.customPlaylistNameHelper}</p>
        </div>
      )}
      {!moodPlaylistForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{mood.autoNameHelp}</p>
      )}
      <div className="space-y-2">
        <Label>{mood.maxTracksLabel}</Label>
        <NumericInput
          placeholder="50"
          value={moodPlaylistForm.max_tracks}
          onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))}
          min={1}
          max={200}
          defaultValue={50}
        />
        <p className="text-xs text-muted-foreground">{mood.maxTracksHelp}</p>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={moodPlaylistForm.exclude_last_run}
          onChange={(e) =>
            setMoodPlaylistForm((prev) => ({
              ...prev,
              exclude_last_run: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{mood.forceFresh}</span>
      </label>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={moodPlaylistForm.limit_by_year}
          onChange={(e) =>
            setMoodPlaylistForm((prev) => ({
              ...prev,
              limit_by_year: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{mood.limitByYear}</span>
      </label>
      {moodPlaylistForm.limit_by_year && (
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{mood.minYear}</Label>
            <NumericInput
              placeholder={mood.minYearPlaceholder}
              value={moodPlaylistForm.min_year}
              onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, min_year: v }))}
              min={1800}
              max={2100}
              defaultValue={1800}
              allowEmpty
            />
          </div>
          <div className="space-y-2">
            <Label>{mood.maxYear}</Label>
            <NumericInput
              placeholder={mood.maxYearPlaceholder}
              value={moodPlaylistForm.max_year}
              onChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, max_year: v }))}
              min={1800}
              max={2100}
              defaultValue={2100}
              allowEmpty
            />
          </div>
        </div>
      )}
      {moodPlaylistForm.limit_by_year && (
        <p className="text-xs text-muted-foreground">{mood.yearRangeHelp}</p>
      )}
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-mood"
        scheduleOverride={moodPlaylistForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setMoodPlaylistForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={moodPlaylistForm.schedule_cron}
        onScheduleCronChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={moodPlaylistForm.enabled}
        onEnabledChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={moodPlaylistForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setMoodPlaylistForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={moodPlaylistForm.expires_at}
        onExpiresAtChange={(v) => setMoodPlaylistForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={moodPlaylistForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setMoodPlaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
