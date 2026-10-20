import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { ps } from "../shared";
import { isCompoundFieldVisible, resolveContextForCreate } from "@/command-spec";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";
import { PlaylistSyncArtistDiscoveryControl } from "@/components/command-edit/PlaylistSyncArtistDiscoveryControl";

export function CommonCreateSettings({ wizard }: { wizard: CreateCommandWizard }) {
  const { playlistType, formData, setFormData, plexAccounts } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{ps.targetLabel}</Label>
        <Select
          value={formData.target}
          onValueChange={(value) =>
            setFormData((prev) => ({
              ...prev,
              target: value,
              sync_to_multiple_plex_users:
                value === "jellyfin" ? false : prev.sync_to_multiple_plex_users,
              plex_account_ids: value === "jellyfin" ? [] : prev.plex_account_ids,
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
      </div>

      {isCompoundFieldVisible(
        "compound.plex_playlist_target",
        resolveContextForCreate({
          playlistType,
          target: formData.target,
        })
      ) && (
        <PlexPlaylistTargetSection
          accounts={plexAccounts}
          syncToMultiple={formData.sync_to_multiple_plex_users}
          selectedAccountIds={formData.plex_account_ids}
          onSyncToMultipleChange={(checked) =>
            setFormData((prev) => ({
              ...prev,
              sync_to_multiple_plex_users: checked,
              plex_account_ids: checked ? prev.plex_account_ids : [],
            }))
          }
          onToggleAccount={(accountId, selected) =>
            setFormData((prev) => ({
              ...prev,
              plex_account_ids: selected
                ? [...prev.plex_account_ids, accountId]
                : prev.plex_account_ids.filter((id) => id !== accountId),
            }))
          }
        />
      )}

      <div className="space-y-2">
        <Label>{ps.syncModeLabel}</Label>
        <Select
          value={formData.sync_mode}
          onValueChange={(value) => setFormData((prev) => ({ ...prev, sync_mode: value }))}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="full">{ps.syncModeFull}</SelectItem>
            <SelectItem value="append">{ps.syncModeAppend}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <CreateCommandScheduleExpiryBlock
        idPrefix="create-ext"
        scheduleOverride={formData.schedule_override}
        onScheduleOverrideChange={(v) => setFormData((prev) => ({ ...prev, schedule_override: v }))}
        scheduleCron={formData.schedule_cron}
        onScheduleCronChange={(v) => setFormData((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={formData.enabled}
        onEnabledChange={(v) => setFormData((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={formData.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setFormData((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={formData.expires_at}
        onExpiresAtChange={(v) => setFormData((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={formData.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setFormData((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      >
        {isCompoundFieldVisible(
          "compound.artist_discovery",
          resolveContextForCreate({
            playlistType,
            target: formData.target,
          })
        ) && (
          <PlaylistSyncArtistDiscoveryControl
            checkboxId="create-enable-artist-discovery"
            value={{
              enable_artist_discovery: formData.enable_artist_discovery,
              artist_discovery_max_per_run:
                formData.artist_discovery_max_per_run ?? (formData.enable_artist_discovery ? 2 : 0),
            }}
            onChange={(next) =>
              setFormData((prev) => ({
                ...prev,
                enable_artist_discovery: next.enable_artist_discovery,
                artist_discovery_max_per_run: next.artist_discovery_max_per_run,
              }))
            }
          />
        )}
      </CreateCommandScheduleExpiryBlock>
    </>
  );
}
