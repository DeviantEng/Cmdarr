import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const t = commandUiCopy.setlistFm;

export function SetlistFmSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{t.artistsLabel}</Label>
        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={editForm.artists ?? ""}
          onChange={(e) => setEditForm((f) => ({ ...f, artists: e.target.value }))}
        />
        <p className="text-xs text-muted-foreground">{t.artistsHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{t.maxTracksPerArtistLabel}</Label>
        <NumericInput
          placeholder="25"
          value={editForm.max_tracks_per_artist ?? 25}
          onChange={(v) => setEditForm((f) => ({ ...f, max_tracks_per_artist: v ?? 25 }))}
          min={3}
          max={30}
          defaultValue={25}
        />
        <p className="text-xs text-muted-foreground">{t.maxTracksPerArtistHelp}</p>
        <p className="text-xs text-muted-foreground">{t.setlistDiscoveryHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{t.targetLabel}</Label>
        <Input
          value={editForm.target === "jellyfin" ? "Jellyfin" : "Plex"}
          disabled
          className="bg-muted"
        />
        <p className="text-xs text-muted-foreground">
          {t.targetWhereHelp} {t.targetReadOnlyHelp}
        </p>
      </div>
      <p className="text-xs text-muted-foreground">{t.setlistNote}</p>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.use_custom_playlist_name ?? false}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{t.useCustomPlaylistName}</span>
      </label>
      {editForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{t.customPlaylistNameLabel}</Label>
          <Input
            value={editForm.custom_playlist_name ?? ""}
            onChange={(e) =>
              setEditForm((f) => ({
                ...f,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={t.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{t.customPlaylistNameHelper}</p>
        </div>
      )}
      {!editForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{t.autoNameHelp}</p>
      )}
    </>
  );
}
