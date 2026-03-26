import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const copy = commandUiCopy.playlistSync.artistDiscovery;

export type ArtistDiscoverySlice = {
  enable_artist_discovery: boolean;
  artist_discovery_max_per_run: number;
};

type Props = {
  value: ArtistDiscoverySlice;
  onChange: (next: ArtistDiscoverySlice) => void;
  checkboxId: string;
};

/**
 * Presentational artist-discovery block (playlist sync / XMPlaylist).
 * Spec copy lives in commandUiCopy; visibility is driven by getFieldsForContext on the parent.
 */
export function PlaylistSyncArtistDiscoveryControl({ value, onChange, checkboxId }: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={checkboxId}
          checked={value.enable_artist_discovery}
          onChange={(e) =>
            onChange({
              ...value,
              enable_artist_discovery: e.target.checked,
            })
          }
          className="rounded border-input"
        />
        <Label htmlFor={checkboxId} className="cursor-pointer font-normal">
          {copy.checkboxLabel}
        </Label>
      </div>
      <p className="text-xs text-muted-foreground">{copy.helper}</p>
      {value.enable_artist_discovery && (
        <div className="space-y-2 rounded-lg border p-4">
          <Label htmlFor={`${checkboxId}-max`}>{copy.maxLabel}</Label>
          <NumericInput
            id={`${checkboxId}-max`}
            placeholder="2"
            value={value.artist_discovery_max_per_run ?? 2}
            onChange={(v) =>
              onChange({
                ...value,
                artist_discovery_max_per_run: v ?? 2,
              })
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
