import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { cw, d } from "../shared";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ExpirationFields } from "@/components/ExpirationFields";

export function DaylistCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { plexAccounts, daylistUsedIds, daylistForm, setDaylistForm } = wizard;
  return (
    <>
      {/* Primary settings */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label>{d.plexAccountLabel}</Label>
          <Select
            value={daylistForm.plex_history_account_id}
            onValueChange={(v) =>
              setDaylistForm((prev) => ({ ...prev, plex_history_account_id: v }))
            }
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
            value={daylistForm.schedule_minute}
            onChange={(v) => setDaylistForm((prev) => ({ ...prev, schedule_minute: v ?? 0 }))}
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
              value={daylistForm.exclude_played_days}
              onChange={(v) => setDaylistForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))}
              min={1}
              max={30}
              defaultValue={3}
            />
            <p className="text-xs text-muted-foreground">{d.excludePlayedHelp}</p>
          </div>
          <div className="space-y-2">
            <Label>{d.historyLookbackLabel}</Label>
            <NumericInput
              value={daylistForm.history_lookback_days}
              onChange={(v) =>
                setDaylistForm((prev) => ({ ...prev, history_lookback_days: v ?? 45 }))
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
              value={daylistForm.max_tracks}
              onChange={(v) => setDaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))}
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
                {d.historicalRatioLabel} {daylistForm.historical_ratio}
              </Label>
              <input
                type="range"
                min={0.1}
                max={0.8}
                step={0.1}
                value={daylistForm.historical_ratio}
                onChange={(e) =>
                  setDaylistForm((prev) => ({
                    ...prev,
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
                value={daylistForm.sonic_similar_limit}
                onChange={(v) =>
                  setDaylistForm((prev) => ({ ...prev, sonic_similar_limit: v ?? 10 }))
                }
                min={1}
                max={30}
                defaultValue={10}
              />
              <p className="text-xs text-muted-foreground">{d.sonicSimilarLimitHelp}</p>
            </div>
            <div className="space-y-2">
              <Label>{d.sonicSimilarPlaylistLimitLabel}</Label>
              <NumericInput
                value={daylistForm.sonic_similarity_limit}
                onChange={(v) =>
                  setDaylistForm((prev) => ({
                    ...prev,
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
                {d.sonicSimilarDistanceLabel} {daylistForm.sonic_similarity_distance}
              </Label>
              <input
                type="range"
                min={0.1}
                max={2}
                step={0.1}
                value={daylistForm.sonic_similarity_distance}
                onChange={(e) =>
                  setDaylistForm((prev) => ({
                    ...prev,
                    sonic_similarity_distance: parseFloat(e.target.value),
                  }))
                }
                className="slider-range"
              />
              <p className="text-xs text-muted-foreground">{d.sonicSimilarDistanceHelp}</p>
            </div>
          </div>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={daylistForm.use_primary_mood}
              onChange={(e) =>
                setDaylistForm((prev) => ({
                  ...prev,
                  use_primary_mood: e.target.checked,
                }))
              }
              className="rounded border-input"
            />
            <span className="text-sm">{d.usePrimaryMood}</span>
          </label>
          <p className="text-xs text-muted-foreground -mt-2">{d.usePrimaryMoodHelp}</p>

          <div className="space-y-2">
            <Label>{d.timezoneLabel}</Label>
            <Input
              placeholder={d.timezonePlaceholder}
              value={daylistForm.timezone}
              onChange={(e) => setDaylistForm((prev) => ({ ...prev, timezone: e.target.value }))}
            />
            <p className="text-xs text-muted-foreground">{d.timezoneHelp}</p>
          </div>

          <div className="space-y-2">
            <Label>{d.timePeriodsLabel}</Label>
            <p className="text-xs text-muted-foreground mb-2">{d.timePeriodsHelp}</p>
            <div className="grid gap-2">
              {Object.entries(daylistForm.time_periods).map(([period, { start, end }]) => (
                <div key={period} className="flex items-center gap-3">
                  <span className="w-28 text-sm">{period}</span>
                  <Input
                    type="text"
                    inputMode="numeric"
                    className="w-16"
                    value={start}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      setDaylistForm((prev) => ({
                        ...prev,
                        time_periods: {
                          ...prev.time_periods,
                          [period]: {
                            ...prev.time_periods[period],
                            start: isNaN(v) ? prev.time_periods[period].start : v,
                          },
                        },
                      }));
                    }}
                  />
                  <span className="text-muted-foreground">–</span>
                  <Input
                    type="text"
                    inputMode="numeric"
                    className="w-16"
                    value={end}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      setDaylistForm((prev) => ({
                        ...prev,
                        time_periods: {
                          ...prev.time_periods,
                          [period]: {
                            ...prev.time_periods[period],
                            end: isNaN(v) ? prev.time_periods[period].end : v,
                          },
                        },
                      }));
                    }}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
      </details>

      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={daylistForm.enabled}
          onChange={(e) => setDaylistForm((prev) => ({ ...prev, enabled: e.target.checked }))}
          className="rounded border-input"
        />
        <span className="text-sm">{cw.enableAfterCreation}</span>
      </label>

      <ExpirationFields
        idPrefix="create-daylist"
        enabled={daylistForm.expires_at_enabled}
        onEnabledChange={(v) =>
          setDaylistForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        value={daylistForm.expires_at}
        onValueChange={(v) => setDaylistForm((prev) => ({ ...prev, expires_at: v }))}
        showDeletePlaylistOption={true}
        deletePlaylistOnExpiry={daylistForm.expires_at_delete_playlist ?? true}
        onDeletePlaylistChange={(v) =>
          setDaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
