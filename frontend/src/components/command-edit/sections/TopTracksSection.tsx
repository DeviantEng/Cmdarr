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
import { commandUiCopy } from "@/command-spec";

export function TopTracksSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>Artists (one per line)</Label>
        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={editForm.artists ?? ""}
          onChange={(e) =>
            setEditForm((f) => ({ ...f, artists: e.target.value }))
          }
        />
        <p className="text-xs text-muted-foreground">
          Artists must exist in your library. Names are validated against the
          library cache.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Top X per artist</Label>
          <NumericInput
            placeholder="5"
            value={editForm.top_x ?? 5}
            onChange={(v) => setEditForm((f) => ({ ...f, top_x: v ?? 5 }))}
            min={1}
            max={20}
            defaultValue={5}
          />
          <p className="text-xs text-muted-foreground">
            Number of top tracks per artist. Min: 1, max: 20.
          </p>
        </div>
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
          <span className="text-sm">Use custom playlist name</span>
        </label>
        {editForm.use_custom_playlist_name && (
          <div className="space-y-2">
            <Label>Custom playlist name</Label>
            <Input
              value={editForm.custom_playlist_name ?? ""}
              onChange={(e) =>
                setEditForm((f) => ({
                  ...f,
                  custom_playlist_name: e.target.value,
                }))
              }
              placeholder="e.g. Road Trip Mix"
            />
            <p className="text-xs text-muted-foreground">
              Override auto-generated name. Shown as [Cmdarr] Artist Essentials:
              &lt;name&gt;.
            </p>
          </div>
        )}
        {!editForm.use_custom_playlist_name && (
          <p className="text-xs text-muted-foreground">
            Playlist name is auto-generated from artist names (e.g. Artist1 ·
            Artist2 + 3 More).
          </p>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{commandUiCopy.xmplaylist.targetReadOnlyLabel}</Label>
          <Input
            value={editForm.target === "jellyfin" ? "Jellyfin" : "Plex"}
            disabled
            className="bg-muted"
          />
          <p className="text-xs text-muted-foreground">
            {commandUiCopy.topTracks.targetReadOnlyHelp}
          </p>
        </div>
        <div className="space-y-2">
          <Label>Source</Label>
          <Select
            value={
              editForm.target === "jellyfin"
                ? "lastfm"
                : (editForm.source ?? "plex")
            }
            disabled={editForm.target === "jellyfin"}
            onValueChange={(v) => setEditForm((f) => ({ ...f, source: v }))}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="plex">Plex</SelectItem>
              <SelectItem value="lastfm">Last.fm</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Plex uses ratingCount; Last.fm uses play counts. Jellyfin requires
            Last.fm.
          </p>
        </div>
      </div>
  </>
    );
}
