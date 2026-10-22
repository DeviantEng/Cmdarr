import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { tt } from "../shared";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

export function TopTracksCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { topTracksForm, setTopTracksForm } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{tt.artistsLabel}</Label>
        <Textarea
          className="min-h-[120px]"
          placeholder={tt.artistsPlaceholder}
          value={topTracksForm.artists}
          onChange={(e) => setTopTracksForm((prev) => ({ ...prev, artists: e.target.value }))}
        />
        <p className="text-xs text-muted-foreground">{tt.artistsHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{tt.topXLabelCreate}</Label>
        <NumericInput
          placeholder="5"
          value={topTracksForm.top_x}
          onChange={(v) => setTopTracksForm((prev) => ({ ...prev, top_x: v ?? 5 }))}
          min={1}
          max={20}
          defaultValue={5}
        />
        <p className="text-xs text-muted-foreground">{tt.topXHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{tt.targetLabel}</Label>
        <Select
          value={topTracksForm.target}
          onValueChange={(v: "plex" | "jellyfin") =>
            setTopTracksForm((prev) => ({
              ...prev,
              target: v,
              source: v === "jellyfin" ? "lastfm" : prev.source,
            }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="plex">Plex</SelectItem>
            <SelectItem value="jellyfin">Jellyfin</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{tt.targetWhereHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{tt.sourceLabelCreate}</Label>
        <Select
          value={topTracksForm.target === "jellyfin" ? "lastfm" : topTracksForm.source}
          disabled={topTracksForm.target === "jellyfin"}
          onValueChange={(v: "plex" | "lastfm") =>
            setTopTracksForm((prev) => ({ ...prev, source: v }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="plex">{tt.plexOptionRating}</SelectItem>
            <SelectItem value="lastfm">{tt.lastfmOption}</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{tt.sourceHelp}</p>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={topTracksForm.use_custom_playlist_name}
          onChange={(e) =>
            setTopTracksForm((prev) => ({
              ...prev,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{tt.useCustomPlaylistName}</span>
      </label>
      {topTracksForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{tt.customPlaylistNameLabel}</Label>
          <Input
            value={topTracksForm.custom_playlist_name}
            onChange={(e) =>
              setTopTracksForm((prev) => ({
                ...prev,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={tt.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{tt.customPlaylistNameHelper}</p>
        </div>
      )}
      {!topTracksForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{tt.autoNameHelp}</p>
      )}
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-tt"
        scheduleOverride={topTracksForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setTopTracksForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={topTracksForm.schedule_cron}
        onScheduleCronChange={(v) => setTopTracksForm((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={topTracksForm.enabled}
        onEnabledChange={(v) => setTopTracksForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={topTracksForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setTopTracksForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={topTracksForm.expires_at}
        onExpiresAtChange={(v) => setTopTracksForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={topTracksForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setTopTracksForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
