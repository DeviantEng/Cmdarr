import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const t = commandUiCopy.lfmSimilar;

export function LfmSimilarSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{t.seedArtistsLabel}</Label>
        <textarea
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          value={editForm.seed_artists ?? ""}
          onChange={(e) => setEditForm((f) => ({ ...f, seed_artists: e.target.value }))}
        />
        <p className="text-xs text-muted-foreground">{t.seedArtistsHelp}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t.similarPerSeedLabel}</Label>
          <NumericInput
            placeholder="5"
            value={editForm.similar_per_seed ?? 5}
            onChange={(v) => setEditForm((f) => ({ ...f, similar_per_seed: v ?? 5 }))}
            min={1}
            max={50}
            defaultValue={5}
          />
          <p className="text-xs text-muted-foreground">{t.similarPerSeedHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{t.maxArtistsLabel}</Label>
          <NumericInput
            placeholder="25"
            value={editForm.max_artists ?? 25}
            onChange={(v) => setEditForm((f) => ({ ...f, max_artists: v ?? 25 }))}
            min={1}
            max={200}
            defaultValue={25}
          />
          <p className="text-xs text-muted-foreground">{t.maxArtistsHelp}</p>
        </div>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={editForm.include_seeds !== false}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              include_seeds: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{t.includeSeedsLabel}</span>
      </label>
      <p className="text-xs text-muted-foreground">{t.includeSeedsHelp}</p>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{t.topXLabel}</Label>
          <NumericInput
            placeholder="5"
            value={editForm.top_x ?? 5}
            onChange={(v) => setEditForm((f) => ({ ...f, top_x: v ?? 5 }))}
            min={1}
            max={20}
            defaultValue={5}
          />
          <p className="text-xs text-muted-foreground">{t.topXHelp}</p>
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
      </div>
      <p className="text-xs text-muted-foreground">{t.lastfmNote}</p>
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
