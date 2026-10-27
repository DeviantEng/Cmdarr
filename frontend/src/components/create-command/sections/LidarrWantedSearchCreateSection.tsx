import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { commandUiCopy } from "@/command-spec";
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";

export function LidarrWantedSearchCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { lidarrWantedSearchForm, setLidarrWantedSearchForm } = wizard;
  return (
    <>
      <p className="text-sm text-muted-foreground">
        Display name is fixed as{" "}
        <span className="font-medium text-foreground">Lidarr Maintenance - Missing Search</span>.
      </p>
      <div className="space-y-2">
        <Label htmlFor="create-lidarr-ws-topx">{commandUiCopy.lidarrMaintenance.topXLabel}</Label>
        <NumericInput
          id="create-lidarr-ws-topx"
          value={lidarrWantedSearchForm.top_x}
          onChange={(v) => setLidarrWantedSearchForm((prev) => ({ ...prev, top_x: v ?? 10 }))}
          min={1}
          max={50}
          defaultValue={10}
        />
        <p className="text-xs text-muted-foreground">{commandUiCopy.lidarrMaintenance.topXHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="create-lidarr-ws-ignore">
          {commandUiCopy.lidarrMaintenance.ignoreDaysLabel}
        </Label>
        <NumericInput
          id="create-lidarr-ws-ignore"
          value={lidarrWantedSearchForm.ignore_days}
          onChange={(v) => setLidarrWantedSearchForm((prev) => ({ ...prev, ignore_days: v ?? 14 }))}
          min={1}
          max={365}
          defaultValue={14}
        />
        <p className="text-xs text-muted-foreground">
          {commandUiCopy.lidarrMaintenance.ignoreDaysHelp}
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="create-lidarr-ws-sort">{commandUiCopy.lidarrMaintenance.sortByLabel}</Label>
        <Select
          value={lidarrWantedSearchForm.sort_by}
          onValueChange={(v) =>
            setLidarrWantedSearchForm((prev) => ({
              ...prev,
              sort_by: v as typeof prev.sort_by,
            }))
          }
        >
          <SelectTrigger id="create-lidarr-ws-sort">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="oldest_release_date">
              {commandUiCopy.lidarrMaintenance.sortOldest}
            </SelectItem>
            <SelectItem value="newest_release_date">
              {commandUiCopy.lidarrMaintenance.sortNewest}
            </SelectItem>
            <SelectItem value="artist_name_asc">
              {commandUiCopy.lidarrMaintenance.sortArtist}
            </SelectItem>
            <SelectItem value="album_title_asc">
              {commandUiCopy.lidarrMaintenance.sortTitle}
            </SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {commandUiCopy.lidarrMaintenance.sortByHelp}
        </p>
      </div>
      <div className="space-y-2">
        <Label>{commandUiCopy.lidarrMaintenance.releaseTypesHeading}</Label>
        <div className="flex flex-wrap gap-4">
          {["album", "ep", "single", "other"].map((t) => (
            <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={lidarrWantedSearchForm.album_types.includes(t)}
                onChange={(e) => {
                  setLidarrWantedSearchForm((prev) => {
                    const next = e.target.checked
                      ? [...prev.album_types, t]
                      : prev.album_types.filter((x) => x !== t);
                    return { ...prev, album_types: next.length ? next : ["album"] };
                  });
                }}
                className="rounded border-input"
              />
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {commandUiCopy.lidarrMaintenance.releaseTypesHelp}
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="create-lidarr-ws-settle">
          {commandUiCopy.lidarrMaintenance.settleSecondsLabel}
        </Label>
        <NumericInput
          id="create-lidarr-ws-settle"
          value={lidarrWantedSearchForm.settle_seconds}
          onChange={(v) =>
            setLidarrWantedSearchForm((prev) => ({ ...prev, settle_seconds: v ?? 30 }))
          }
          min={0}
          max={300}
          defaultValue={15}
        />
        <p className="text-xs text-muted-foreground">
          {commandUiCopy.lidarrMaintenance.settleSecondsHelp}
        </p>
      </div>
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-lidarr-ws"
        scheduleOverride={lidarrWantedSearchForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setLidarrWantedSearchForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={lidarrWantedSearchForm.schedule_cron}
        onScheduleCronChange={(v) =>
          setLidarrWantedSearchForm((prev) => ({ ...prev, schedule_cron: v }))
        }
        enabled={lidarrWantedSearchForm.enabled}
        onEnabledChange={(v) => setLidarrWantedSearchForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={false}
        onExpiresAtEnabledChange={() => {}}
        expiresAt=""
        onExpiresAtChange={() => {}}
        expiresAtDeletePlaylist={false}
        onExpiresAtDeletePlaylistChange={() => {}}
        showExpiration={false}
      />
    </>
  );
}
