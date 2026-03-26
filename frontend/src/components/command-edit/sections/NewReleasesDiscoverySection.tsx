import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const nr = commandUiCopy.newReleases;

export function NewReleasesDiscoverySection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, nrdSources } = ctx;
  const spotify = nrdSources.find((s) => s.id === "spotify");
  const spotifyConfigured = !!spotify?.configured;
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-artists">{nr.artistsPerRun}</Label>
        <NumericInput
          id="edit-artists"
          value={editForm.artists_per_run ?? 5}
          onChange={(v) => setEditForm((f) => ({ ...f, artists_per_run: v ?? 5 }))}
          min={1}
          max={50}
          defaultValue={5}
        />
        <p className="text-xs text-muted-foreground">{nr.artistsPerRunHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-source">{nr.releaseSource}</Label>
        <select
          id="edit-source"
          value={editForm.new_releases_source ?? "deezer"}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              new_releases_source: e.target.value === "spotify" ? "spotify" : "deezer",
            }))
          }
          className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
        >
          <option value="deezer">{nr.deezerOption}</option>
          <option value="spotify" disabled={!!spotify && !spotify.configured}>
            {`${nr.spotifyOptionPrefix}${spotifyConfigured ? nr.spotifyCredentialsOk : nr.spotifyCredentialsMissing})`}
          </option>
        </select>
        <p className="text-xs text-muted-foreground">{nr.sourceHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{nr.releaseTypesHeading}</Label>
        <div className="flex flex-wrap gap-4">
          {["album", "ep", "single", "other"].map((t) => (
            <label key={t} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="checkbox"
                checked={(editForm.album_types ?? ["album"]).includes(t)}
                onChange={(e) => {
                  setEditForm((f) => {
                    const current = f.album_types ?? ["album"];
                    const next = e.target.checked
                      ? [...current, t]
                      : current.filter((x) => x !== t);
                    return { ...f, album_types: next.length ? next : ["album"] };
                  });
                }}
                className="rounded border-input"
              />
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">{nr.releaseTypesHelp}</p>
      </div>
    </>
  );
}
