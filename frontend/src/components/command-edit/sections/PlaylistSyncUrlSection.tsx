import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { commandUiCopy } from "@/command-spec";

export function PlaylistSyncUrlSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand, editForm, setEditForm } = ctx;
  const ps = commandUiCopy.playlistSync;
  return (
    <>
      <div className="space-y-2">
        <Label>{ps.playlistUrlLabel}</Label>
        <Input
          value={String(editingCommand.config_json?.playlist_url ?? "")}
          disabled
          className="font-mono text-sm"
        />
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
        <span className="text-sm">{ps.useCustomPlaylistName}</span>
      </label>
      {editForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{ps.customPlaylistNameLabel}</Label>
          <Input
            value={editForm.custom_playlist_name ?? ""}
            onChange={(e) =>
              setEditForm((f) => ({
                ...f,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={ps.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{ps.customPlaylistNameHelper}</p>
        </div>
      )}
      {!editForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{ps.autoNameHelp}</p>
      )}
    </>
  );
}
