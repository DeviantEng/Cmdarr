import { useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Label } from "@/components/ui/label";

function commandCreatesPlaylist(commandName: string): boolean {
  return (
    commandName.startsWith("playlist_sync_") ||
    commandName.startsWith("top_tracks_") ||
    commandName.startsWith("lfm_similar_") ||
    commandName.startsWith("setlistfm_") ||
    commandName.startsWith("mood_playlist_") ||
    commandName.startsWith("xmplaylist_") ||
    commandName.startsWith("daylist_") ||
    commandName.startsWith("local_discovery_")
  );
}

type DeleteCommandDialogProps = {
  open: boolean;
  commandName: string | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (deletePlaylist: boolean) => void | Promise<void>;
  isDeleting?: boolean;
};

export function DeleteCommandDialog({
  open,
  commandName,
  onOpenChange,
  onConfirm,
  isDeleting = false,
}: DeleteCommandDialogProps) {
  const [deletePlaylist, setDeletePlaylist] = useState(false);

  const showPlaylistOption = commandName ? commandCreatesPlaylist(commandName) : false;

  const handleOpenChange = (next: boolean) => {
    if (!next) setDeletePlaylist(false);
    onOpenChange(next);
  };

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Delete command"
      description={
        commandName
          ? `Are you sure you want to delete "${commandName}"? This cannot be undone.`
          : "Are you sure you want to delete this command? This cannot be undone."
      }
      confirmLabel="Delete"
      cancelLabel="Cancel"
      variant="destructive"
      isLoading={isDeleting}
      onConfirm={() => onConfirm(deletePlaylist)}
    >
      {showPlaylistOption && (
        <div className="flex items-start gap-2 py-2">
          <input
            type="checkbox"
            id="delete-playlist-on-command-delete"
            checked={deletePlaylist}
            onChange={(e) => setDeletePlaylist(e.target.checked)}
            className="mt-1 rounded border-input"
          />
          <Label htmlFor="delete-playlist-on-command-delete" className="cursor-pointer font-normal">
            Also delete playlist from Plex/Jellyfin
          </Label>
        </div>
      )}
    </ConfirmDialog>
  );
}
