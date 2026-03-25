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

export function DaylistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, plexAccounts, daylistUsedIds } = ctx;
  return (
    <>
      {/* Primary settings */}
      <div className="space-y-4">
        <div className="space-y-2">
          <Label>Plex Account (play history source)</Label>
          <Select
            value={editForm.plex_history_account_id ?? ""}
            onValueChange={(v) =>
              setEditForm((f) => ({ ...f, plex_history_account_id: v }))
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Select Plex account" />
            </SelectTrigger>
            <SelectContent>
              {plexAccounts.map((acc) => (
                <SelectItem
                  key={acc.id}
                  value={acc.id}
                  disabled={daylistUsedIds.has(acc.id)}
                >
                  {acc.name || `Account ${acc.id}`}
                  {daylistUsedIds.has(acc.id) ? " (already has Daylist)" : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Plex Home users only. Daylist uses this account&apos;s play history.
            One Daylist per user.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Run at minute of hour (0–59)</Label>
          <NumericInput
            value={editForm.schedule_minute ?? 0}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, schedule_minute: v ?? 0 }))
            }
            min={0}
            max={59}
            defaultValue={0}
          />
          <p className="text-xs text-muted-foreground">
            Daylist runs hourly at this minute. Runs only when the day period
            changes (Dawn, Morning, etc.). Min: 0, max: 59.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Exclude played (days)</Label>
            <NumericInput
              value={editForm.exclude_played_days ?? 3}
              onChange={(v) =>
                setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))
              }
              min={1}
              max={30}
              defaultValue={3}
            />
            <p className="text-xs text-muted-foreground">
              Skip tracks played in last N days. Min: 1, max: 30.
            </p>
          </div>
          <div className="space-y-2">
            <Label>History lookback (days)</Label>
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
            <p className="text-xs text-muted-foreground">
              Days of play history to analyze. Min: 7, max: 365.
            </p>
          </div>
          <div className="space-y-2">
            <Label>Max tracks</Label>
            <NumericInput
              value={editForm.max_tracks ?? 50}
              onChange={(v) =>
                setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))
              }
              min={10}
              max={200}
              defaultValue={50}
            />
            <p className="text-xs text-muted-foreground">
              Target playlist size. Min: 10, max: 200.
            </p>
          </div>
        </div>
      </div>
  
      {/* Advanced settings (collapsible) */}
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer font-medium text-sm text-muted-foreground hover:text-foreground transition-colors">
          Advanced settings
        </summary>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Historical ratio: {editForm.historical_ratio ?? 0.4}</Label>
              <input
                type="range"
                min={0.1}
                max={0.8}
                step={0.1}
                value={editForm.historical_ratio ?? 0.4}
                onChange={(e) =>
                  setEditForm((f) => ({
                    ...f,
                    historical_ratio: parseFloat(e.target.value),
                  }))
                }
                className="slider-range"
              />
              <p className="text-xs text-muted-foreground">
                Share of tracks from history. Min: 0.1, max: 0.8.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Sonically similar limit</Label>
              <NumericInput
                value={editForm.sonic_similar_limit ?? 10}
                onChange={(v) =>
                  setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 10 }))
                }
                min={1}
                max={30}
                defaultValue={10}
              />
              <p className="text-xs text-muted-foreground">
                Max similar tracks per seed. Min: 1, max: 30.
              </p>
            </div>
            <div className="space-y-2">
              <Label>Sonically similar playlist limit</Label>
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
              <p className="text-xs text-muted-foreground">
                Max tracks to fetch from Plex sonic API per request. Min: 10, max:
                200.
              </p>
            </div>
            <div className="space-y-2">
              <Label>
                Sonically similar distance:{" "}
                {editForm.sonic_similarity_distance ?? 0.8}
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
              <p className="text-xs text-muted-foreground">
                0.1 = very similar, 2 = more diverse. Min: 0.1, max: 2.
              </p>
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
              Use primary mood for cover (default: secondary)
            </Label>
          </div>
          <p className="text-xs text-muted-foreground -mt-2">
            Cover text uses the second-most-common mood by default (Meloday).
            Enable to use the most common mood instead.
          </p>
          <div className="space-y-2">
            <Label>Timezone (optional)</Label>
            <Input
              placeholder="e.g. America/New_York"
              value={editForm.timezone ?? ""}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, timezone: e.target.value }))
              }
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to use scheduler timezone
            </p>
          </div>
          <div className="space-y-2">
            <Label>Time periods (Start–End hour, 0–23)</Label>
            <p className="text-xs text-muted-foreground mb-2">
              When each period runs. Late Night wraps (e.g. 22–2 = 22,23,0,1,2).
              Hours 0–23.
            </p>
            <div className="grid gap-2">
              {Object.entries(
                editForm.time_periods ?? DEFAULT_DAYLIST_TIME_PERIODS
              ).map(([period, { start, end }]) => (
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
              ))}
            </div>
          </div>
        </div>
      </details>
  </>
    );
}
