import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DEFAULT_DAYLIST_TIME_PERIODS } from "../daylistTime";
import { commandUiCopy } from "@/command-spec";

const d = commandUiCopy.daylist;

export function DaylistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, plexAccounts, daylistUsedIds } = ctx;
  return (
    <>
      {/* Primary settings */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label>{d.plexAccountLabel}</Label>
          <Select
            value={editForm.plex_history_account_id ?? ""}
            onValueChange={(v) => setEditForm((f) => ({ ...f, plex_history_account_id: v }))}
          >
            <SelectTrigger>
              <SelectValue placeholder={d.selectPlexPlaceholder} />
            </SelectTrigger>
            <SelectContent>
              {plexAccounts.map((acc) => (
                <SelectItem key={acc.id} value={acc.id} disabled={daylistUsedIds.has(acc.id)}>
                  {acc.name || `Account ${acc.id}`}
                  {daylistUsedIds.has(acc.id) ? d.accountSuffixInUse : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{d.plexAccountHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{d.runAtMinuteLabel}</Label>
          <NumericInput
            value={editForm.schedule_minute ?? 0}
            onChange={(v) => setEditForm((f) => ({ ...f, schedule_minute: v ?? 0 }))}
            min={0}
            max={59}
            defaultValue={0}
          />
          <p className="text-xs text-muted-foreground">{d.runAtMinuteHelp}</p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>{d.excludePlayedLabel}</Label>
            <NumericInput
              value={editForm.exclude_played_days ?? 3}
              onChange={(v) => setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))}
              min={1}
              max={30}
              defaultValue={3}
            />
            <p className="text-xs text-muted-foreground">{d.excludePlayedHelp}</p>
          </div>
          <div className="space-y-2">
            <Label>{d.historyLookbackLabel}</Label>
            <NumericInput
              value={editForm.history_lookback_days ?? 45}
              onChange={(v) =>
                setEditForm((f) => ({
                  ...f,
                  history_lookback_days: v ?? 45,
                }))
              }
              min={7}
              max={365}
              defaultValue={45}
            />
            <p className="text-xs text-muted-foreground">{d.historyLookbackHelp}</p>
          </div>
          <div className="space-y-2">
            <Label>{d.maxTracksLabel}</Label>
            <NumericInput
              value={editForm.max_tracks ?? 50}
              onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
              min={10}
              max={200}
              defaultValue={50}
            />
            <p className="text-xs text-muted-foreground">{d.maxTracksHelp}</p>
          </div>
        </div>
      </div>

      {/* Advanced settings (collapsible) */}
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer font-medium text-sm text-muted-foreground hover:text-foreground transition-colors">
          {d.advancedSummary}
        </summary>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>
                {d.historicalRatioLabel} {editForm.historical_ratio ?? 0.3}
              </Label>
              <input
                type="range"
                min={0.1}
                max={0.8}
                step={0.1}
                value={editForm.historical_ratio ?? 0.3}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    historical_ratio: parseFloat(e.target.value),
                  }))
                }
                className="slider-range"
              />
              <p className="text-xs text-muted-foreground">{d.historicalRatioHelp}</p>
            </div>
            <div className="space-y-2">
              <Label>{d.sonicSimilarLimitLabel}</Label>
              <NumericInput
                value={editForm.sonic_similar_limit ?? 10}
                onChange={(v) => setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 10 }))}
                min={1}
                max={30}
                defaultValue={10}
              />
              <p className="text-xs text-muted-foreground">{d.sonicSimilarLimitHelp}</p>
            </div>
            <div className="space-y-2">
              <Label>{d.sonicSimilarPlaylistLimitLabel}</Label>
              <NumericInput
                value={editForm.sonic_similarity_limit ?? 50}
                onChange={(v) =>
                  setEditForm((f) => ({
                    ...f,
                    sonic_similarity_limit: v ?? 50,
                  }))
                }
                min={10}
                max={200}
                defaultValue={50}
              />
              <p className="text-xs text-muted-foreground">{d.sonicSimilarPlaylistLimitHelp}</p>
            </div>
            <div className="space-y-2">
              <Label>
                {d.sonicSimilarDistanceLabel} {editForm.sonic_similarity_distance ?? 0.8}
              </Label>
              <input
                type="range"
                min={0.1}
                max={2}
                step={0.1}
                value={editForm.sonic_similarity_distance ?? 0.8}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    sonic_similarity_distance: parseFloat(e.target.value) || 0.8,
                  }))
                }
                className="slider-range"
              />
              <p className="text-xs text-muted-foreground">{d.sonicSimilarDistanceHelp}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="edit-use-primary-mood"
              checked={editForm.use_primary_mood ?? false}
              onChange={(e) =>
                setEditForm((f) => ({
                  ...f,
                  use_primary_mood: e.target.checked,
                }))
              }
              className="rounded border-input"
            />
            <Label htmlFor="edit-use-primary-mood" className="font-normal">
              {d.usePrimaryMood}
            </Label>
          </div>
          <p className="text-xs text-muted-foreground -mt-2">{d.usePrimaryMoodHelp}</p>
          <div className="space-y-2">
            <Label>{d.timezoneLabel}</Label>
            <Input
              placeholder={d.timezonePlaceholder}
              value={editForm.timezone ?? ""}
              onChange={(e) => setEditForm((f) => ({ ...f, timezone: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">{d.timezoneHelp}</p>
          </div>
          <div className="space-y-2">
            <Label>{d.timePeriodsLabel}</Label>
            <p className="text-xs text-muted-foreground mb-2">{d.timePeriodsHelp}</p>
            <div className="grid gap-2">
              {Object.entries(editForm.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS).map(
                ([period, { start, end }]) => (
                  <div key={period} className="flex items-center gap-3">
                    <span className="w-28 text-sm">{period}</span>
                    <NumericInput
                      className="w-16"
                      value={start}
                      onChange={(v) =>
                        setEditForm((f) => ({
                          ...f,
                          time_periods: {
                            ...(f.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS),
                            [period]: {
                              ...(f.time_periods?.[period] ?? { start: 0, end: 0 }),
                              start: v ?? f.time_periods?.[period]?.start ?? 0,
                            },
                          },
                        }))
                      }
                      min={0}
                      max={23}
                      defaultValue={0}
                    />
                    <span className="text-muted-foreground">–</span>
                    <NumericInput
                      className="w-16"
                      value={end}
                      onChange={(v) =>
                        setEditForm((f) => ({
                          ...f,
                          time_periods: {
                            ...(f.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS),
                            [period]: {
                              ...(f.time_periods?.[period] ?? { start: 0, end: 0 }),
                              end: v ?? f.time_periods?.[period]?.end ?? 0,
                            },
                          },
                        }))
                      }
                      min={0}
                      max={23}
                      defaultValue={0}
                    />
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      </details>
    </>
  );
}
