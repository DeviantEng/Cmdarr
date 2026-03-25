import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";
import type { CommandEditFormState } from "./types";
import type { Dispatch, SetStateAction } from "react";

const copy = commandUiCopy.playlistSync.artistDiscovery;

type Props = {
  editForm: CommandEditFormState;
  setEditForm: Dispatch<SetStateAction<CommandEditFormState>>;
  checkboxId?: string;
};

/** Shared playlist_sync / playlist_generator artist discovery (Lidarr import list). */
export function ArtistDiscoveryFields({
  editForm,
  setEditForm,
  checkboxId = "edit-artist-discovery-shared",
}: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={checkboxId}
          checked={editForm.enable_artist_discovery ?? false}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              enable_artist_discovery: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <Label htmlFor={checkboxId} className="cursor-pointer font-normal">
          {copy.checkboxLabel}
        </Label>
      </div>
      <p className="text-xs text-muted-foreground">{copy.helper}</p>
      {editForm.enable_artist_discovery && (
        <div className="space-y-2 rounded-lg border p-4">
          <Label htmlFor={`${checkboxId}-max`}>{copy.maxLabel}</Label>
          <NumericInput
            id={`${checkboxId}-max`}
            placeholder="2"
            value={editForm.artist_discovery_max_per_run ?? 2}
            onChange={(v) =>
              setEditForm((f) => ({
                ...f,
                artist_discovery_max_per_run: v ?? 2,
              }))
            }
            min={0}
            max={50}
            defaultValue={2}
          />
          <p className="text-xs text-muted-foreground">{copy.maxHelper}</p>
        </div>
      )}
    </div>
  );
}
