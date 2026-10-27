import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { sf } from "../shared";
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

export function SetlistFmCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { setlistfmForm, setSetlistfmForm } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{sf.artistsLabel}</Label>
        <Textarea
          className="min-h-[120px]"
          placeholder={sf.artistsPlaceholder}
          value={setlistfmForm.artists}
          onChange={(e) => setSetlistfmForm((prev) => ({ ...prev, artists: e.target.value }))}
        />
        <p className="text-xs text-muted-foreground">{sf.artistsHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{sf.maxTracksPerArtistLabel}</Label>
        <NumericInput
          placeholder="25"
          value={setlistfmForm.max_tracks_per_artist}
          onChange={(v) =>
            setSetlistfmForm((prev) => ({
              ...prev,
              max_tracks_per_artist: v ?? 25,
            }))
          }
          min={3}
          max={30}
          defaultValue={25}
        />
        <p className="text-xs text-muted-foreground">{sf.maxTracksPerArtistHelp}</p>
        <p className="text-xs text-muted-foreground">{sf.setlistDiscoveryHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{sf.targetLabel}</Label>
        <Select
          value={setlistfmForm.target}
          onValueChange={(v: "plex" | "jellyfin") =>
            setSetlistfmForm((prev) => ({ ...prev, target: v }))
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
        <p className="text-xs text-muted-foreground">{sf.targetWhereHelp}</p>
      </div>
      <p className="text-xs text-muted-foreground">{sf.setlistNote}</p>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={setlistfmForm.use_custom_playlist_name}
          onChange={(e) =>
            setSetlistfmForm((prev) => ({
              ...prev,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{sf.useCustomPlaylistName}</span>
      </label>
      {setlistfmForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{sf.customPlaylistNameLabel}</Label>
          <Input
            value={setlistfmForm.custom_playlist_name}
            onChange={(e) =>
              setSetlistfmForm((prev) => ({
                ...prev,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={sf.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{sf.customPlaylistNameHelper}</p>
        </div>
      )}
      {!setlistfmForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{sf.autoNameHelp}</p>
      )}
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-sf"
        scheduleOverride={setlistfmForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setSetlistfmForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={setlistfmForm.schedule_cron}
        onScheduleCronChange={(v) => setSetlistfmForm((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={setlistfmForm.enabled}
        onEnabledChange={(v) => setSetlistfmForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={setlistfmForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setSetlistfmForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={setlistfmForm.expires_at}
        onExpiresAtChange={(v) => setSetlistfmForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={setlistfmForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setSetlistfmForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
