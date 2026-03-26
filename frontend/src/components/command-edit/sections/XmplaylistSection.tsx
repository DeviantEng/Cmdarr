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
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";
import {
  commandUiCopy,
  isCompoundFieldVisible,
  resolveContextForEditCommand,
} from "@/command-spec";
import { ArtistDiscoveryFields } from "../ArtistDiscoveryFields";

const xm = commandUiCopy.xmplaylist;

export function XmplaylistSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const {
    editForm,
    setEditForm,
    plexAccounts,
    xmplaylistEditFilter,
    setXmplaylistEditFilter,
    xmplaylistEditLoading,
    filteredXmEditStations,
    editingCommand,
  } = ctx;
  const r = resolveContextForEditCommand(editingCommand);

  return (
    <>
      <div className="space-y-2">
        <Label>{xm.stationLabel}</Label>
        <Input
          placeholder={xm.filterStationsPlaceholder}
          value={xmplaylistEditFilter}
          onChange={(e) => setXmplaylistEditFilter(e.target.value)}
          disabled={xmplaylistEditLoading}
        />
        <p className="text-xs text-muted-foreground">
          {xm.currentSelectionPrefix}{" "}
          {editForm.xm_station_display_name || editForm.xm_station_deeplink || "—"}
        </p>
        <div className="max-h-40 overflow-y-auto rounded-md border border-input">
          {xmplaylistEditLoading ? (
            <p className="p-2 text-sm text-muted-foreground">{xm.loadingEllipsis}</p>
          ) : (
            filteredXmEditStations.map((s) => (
              <button
                key={s.deeplink}
                type="button"
                className="block w-full border-b border-border px-2 py-1.5 text-left text-sm last:border-b-0 hover:bg-accent"
                onClick={() =>
                  setEditForm((f) => ({
                    ...f,
                    xm_station_deeplink: s.deeplink,
                    xm_station_display_name: s.name,
                  }))
                }
              >
                {s.label}
              </button>
            ))
          )}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{xm.playlistModeLabel}</Label>
          <Input
            value={
              editForm.xm_playlist_kind === "most_heard"
                ? xm.modeDisplayMostPlayed
                : xm.modeDisplayNewest
            }
            disabled
            className="bg-muted"
          />
          <p className="text-xs text-muted-foreground">{xm.sourceLockedHint}</p>
        </div>
        {editForm.xm_playlist_kind === "most_heard" && (
          <div className="space-y-2">
            <Label>{xm.daysLabel}</Label>
            <Select
              value={String(editForm.xm_most_heard_days ?? 30)}
              onValueChange={(v) =>
                setEditForm((f) => ({
                  ...f,
                  xm_most_heard_days: parseInt(v, 10),
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1</SelectItem>
                <SelectItem value="7">7</SelectItem>
                <SelectItem value="14">14</SelectItem>
                <SelectItem value="30">30</SelectItem>
                <SelectItem value="60">60</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
      <div className="space-y-2">
        <Label>{xm.maxTracksLabel}</Label>
        <NumericInput
          value={editForm.max_tracks ?? 50}
          onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
          min={1}
          max={50}
          defaultValue={50}
        />
        <p className="text-xs text-muted-foreground">{xm.maxTracksHelpRange}</p>
      </div>
      <div className="space-y-2">
        <Label>{xm.targetReadOnlyLabel}</Label>
        <Input
          value={editForm.target === "jellyfin" ? "Jellyfin" : "Plex"}
          disabled
          className="bg-muted"
        />
        <p className="text-xs text-muted-foreground">{xm.targetReadOnlyHelp}</p>
      </div>
      {isCompoundFieldVisible("compound.plex_playlist_target", r) && (
        <PlexPlaylistTargetSection
          accounts={plexAccounts}
          syncToMultiple={!!editForm.sync_to_multiple_plex_users}
          selectedAccountIds={editForm.plex_account_ids ?? []}
          onSyncToMultipleChange={(checked) =>
            setEditForm((f) => ({
              ...f,
              sync_to_multiple_plex_users: checked,
              plex_account_ids: checked ? (f.plex_account_ids ?? []) : [],
            }))
          }
          onToggleAccount={(accountId, selected) =>
            setEditForm((f) => ({
              ...f,
              plex_account_ids: selected
                ? [...(f.plex_account_ids ?? []), accountId]
                : (f.plex_account_ids ?? []).filter((id) => id !== accountId),
            }))
          }
        />
      )}
      {isCompoundFieldVisible("compound.artist_discovery", r) && (
        <ArtistDiscoveryFields
          editForm={editForm}
          setEditForm={setEditForm}
          checkboxId="edit-xm-enable-artist-discovery"
        />
      )}
    </>
  );
}
