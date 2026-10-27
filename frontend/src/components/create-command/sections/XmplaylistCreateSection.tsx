import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { xm, ps } from "../shared";
import { isCompoundFieldVisible, resolveContextForCreate } from "@/command-spec";
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
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";
import { PlaylistSyncArtistDiscoveryControl } from "@/components/command-edit/PlaylistSyncArtistDiscoveryControl";

export function XmplaylistCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const {
    plexAccounts,
    xmplaylistForm,
    setXmplaylistForm,
    xmplaylistStationsLoading,
    xmplaylistStationFilter,
    setXmplaylistStationFilter,
    filteredXmStations,
  } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{xm.stationLabel}</Label>
        <p className="text-xs text-muted-foreground">{xm.stationSearchHint}</p>
        {xmplaylistForm.station_label ? (
          <p className="text-sm font-medium">
            {xm.selectedStationLabel} {xmplaylistForm.station_label}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">{xm.noStationSelected}</p>
        )}
        <Input
          placeholder={xm.filterStationsPlaceholder}
          value={xmplaylistStationFilter}
          onChange={(e) => setXmplaylistStationFilter(e.target.value)}
          disabled={xmplaylistStationsLoading}
        />
        <div className="max-h-40 overflow-y-auto rounded-md border border-input">
          {xmplaylistStationsLoading ? (
            <p className="p-3 text-sm text-muted-foreground">{xm.loadingStations}</p>
          ) : filteredXmStations.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">{xm.noStationsMatch}</p>
          ) : (
            filteredXmStations.map((s) => (
              <button
                key={s.deeplink}
                type="button"
                className="block w-full border-b border-border px-3 py-1.5 text-left text-sm last:border-b-0 hover:bg-accent"
                onClick={() =>
                  setXmplaylistForm((prev) => ({
                    ...prev,
                    station_deeplink: s.deeplink,
                    station_display_name: s.name,
                    station_label: s.label,
                  }))
                }
              >
                {s.label}
              </button>
            ))
          )}
        </div>
      </div>
      <div className="space-y-2">
        <Label>{xm.playlistSourceLabel}</Label>
        <Select
          value={xmplaylistForm.playlist_kind}
          onValueChange={(v: "newest" | "most_heard") =>
            setXmplaylistForm((prev) => ({ ...prev, playlist_kind: v }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="newest">{xm.newestTracksOption}</SelectItem>
            <SelectItem value="most_heard">{xm.mostPlayedOption}</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {xmplaylistForm.playlist_kind === "most_heard" && (
        <div className="space-y-2">
          <Label>{xm.timePeriodLabel}</Label>
          <Select
            value={String(xmplaylistForm.most_heard_days)}
            onValueChange={(v) =>
              setXmplaylistForm((prev) => ({
                ...prev,
                most_heard_days: parseInt(v, 10) as 1 | 7 | 14 | 30 | 60,
              }))
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">{xm.period1Day}</SelectItem>
              <SelectItem value="7">{xm.period7Days}</SelectItem>
              <SelectItem value="14">{xm.period14Days}</SelectItem>
              <SelectItem value="30">{xm.period30Days}</SelectItem>
              <SelectItem value="60">{xm.period60Days}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="space-y-2">
        <Label>{xm.maxTracksInPlaylistLabel}</Label>
        <NumericInput
          value={xmplaylistForm.max_tracks}
          onChange={(v) => setXmplaylistForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))}
          min={1}
          max={50}
          defaultValue={50}
        />
        <p className="text-xs text-muted-foreground">{xm.maxTracksHelpRange}</p>
      </div>
      <div className="space-y-2">
        <Label>{ps.targetLabel}</Label>
        <Select
          value={xmplaylistForm.target}
          onValueChange={(v: "plex" | "jellyfin") =>
            setXmplaylistForm((prev) => ({
              ...prev,
              target: v,
              sync_to_multiple_plex_users:
                v === "jellyfin" ? false : prev.sync_to_multiple_plex_users,
              plex_account_ids: v === "jellyfin" ? [] : prev.plex_account_ids,
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
          playlistType: "xmplaylist",
          target: xmplaylistForm.target,
        })
      ) && (
        <PlexPlaylistTargetSection
          accounts={plexAccounts}
          syncToMultiple={xmplaylistForm.sync_to_multiple_plex_users}
          selectedAccountIds={xmplaylistForm.plex_account_ids}
          onSyncToMultipleChange={(checked) =>
            setXmplaylistForm((prev) => ({
              ...prev,
              sync_to_multiple_plex_users: checked,
              plex_account_ids: checked ? prev.plex_account_ids : [],
            }))
          }
          onToggleAccount={(accountId, selected) =>
            setXmplaylistForm((prev) => ({
              ...prev,
              plex_account_ids: selected
                ? [...prev.plex_account_ids, accountId]
                : prev.plex_account_ids.filter((id) => id !== accountId),
            }))
          }
        />
      )}
      {isCompoundFieldVisible(
        "compound.artist_discovery",
        resolveContextForCreate({
          playlistType: "xmplaylist",
          target: xmplaylistForm.target,
        })
      ) && (
        <PlaylistSyncArtistDiscoveryControl
          checkboxId="create-xm-artist-discovery"
          value={{
            enable_artist_discovery: xmplaylistForm.enable_artist_discovery,
            artist_discovery_max_per_run: xmplaylistForm.artist_discovery_max_per_run ?? 2,
          }}
          onChange={(next) =>
            setXmplaylistForm((prev) => ({
              ...prev,
              enable_artist_discovery: next.enable_artist_discovery,
              artist_discovery_max_per_run: next.artist_discovery_max_per_run,
            }))
          }
        />
      )}
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-xm"
        scheduleOverride={xmplaylistForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setXmplaylistForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={xmplaylistForm.schedule_cron}
        onScheduleCronChange={(v) => setXmplaylistForm((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={xmplaylistForm.enabled}
        onEnabledChange={(v) => setXmplaylistForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={xmplaylistForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setXmplaylistForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={xmplaylistForm.expires_at}
        onExpiresAtChange={(v) => setXmplaylistForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={xmplaylistForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setXmplaylistForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
