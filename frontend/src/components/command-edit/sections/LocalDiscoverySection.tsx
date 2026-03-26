import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { commandUiCopy } from "@/command-spec";

const ld = commandUiCopy.localDiscovery;

export function LocalDiscoverySection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, plexAccounts, localDiscoveryUsedIds } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{ld.plexAccountLabel}</Label>
        <Select
          value={editForm.plex_history_account_id ?? ""}
          onValueChange={(v) => setEditForm((f) => ({ ...f, plex_history_account_id: v }))}
        >
          <SelectTrigger>
            <SelectValue placeholder={ld.selectPlaceholder} />
          </SelectTrigger>
          <SelectContent>
            {plexAccounts.map((acc) => (
              <SelectItem key={acc.id} value={acc.id} disabled={localDiscoveryUsedIds.has(acc.id)}>
                {acc.name || acc.id}
                {localDiscoveryUsedIds.has(acc.id) ? ld.accountSuffixInUse : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{ld.plexAccountHelp}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{ld.lookbackDaysLabel}</Label>
          <NumericInput
            value={editForm.lookback_days ?? 90}
            onChange={(v) => setEditForm((f) => ({ ...f, lookback_days: v ?? 90 }))}
            min={7}
            max={365}
            defaultValue={90}
          />
          <p className="text-xs text-muted-foreground">{ld.lookbackDaysHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.excludePlayedLabel}</Label>
          <NumericInput
            value={editForm.exclude_played_days ?? 3}
            onChange={(v) => setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))}
            min={0}
            max={30}
            defaultValue={3}
          />
          <p className="text-xs text-muted-foreground">{ld.excludePlayedHelp}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{ld.topArtistsCountLabel}</Label>
          <NumericInput
            value={editForm.top_artists_count ?? 10}
            onChange={(v) => setEditForm((f) => ({ ...f, top_artists_count: v ?? 10 }))}
            min={1}
            max={20}
            defaultValue={10}
          />
          <p className="text-xs text-muted-foreground">{ld.topArtistsCountHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.artistPoolSizeLabel}</Label>
          <NumericInput
            value={editForm.artist_pool_size ?? 20}
            onChange={(v) => setEditForm((f) => ({ ...f, artist_pool_size: v ?? 20 }))}
            min={1}
            max={50}
            defaultValue={20}
          />
          <p className="text-xs text-muted-foreground">{ld.artistPoolSizeHelp}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{ld.maxTracksLabel}</Label>
          <NumericInput
            value={editForm.max_tracks ?? 50}
            onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
            min={1}
            max={200}
            defaultValue={50}
          />
          <p className="text-xs text-muted-foreground">{ld.maxTracksHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.sonicSimilarLimitLabel}</Label>
          <NumericInput
            value={editForm.sonic_similar_limit ?? 15}
            onChange={(v) => setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 15 }))}
            min={5}
            max={50}
            defaultValue={15}
          />
          <p className="text-xs text-muted-foreground">{ld.sonicSimilarLimitHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.sonicSimilarityDistanceLabel}</Label>
          <NumericInput
            value={editForm.sonic_similarity_distance ?? 0.25}
            onChange={(v) =>
              setEditForm((f) => ({
                ...f,
                sonic_similarity_distance: v ?? 0.25,
              }))
            }
            min={0.1}
            max={1}
            defaultValue={0.25}
            numericType="float"
          />
          <p className="text-xs text-muted-foreground">{ld.sonicSimilarityDistanceHelp}</p>
        </div>
      </div>
      <div className="space-y-2">
        <Label>
          {ld.historicalRatioLabel} {editForm.historical_ratio ?? 0.4}
        </Label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.1"
          value={editForm.historical_ratio ?? 0.4}
          onChange={(e) =>
            setEditForm((f) => ({
              ...f,
              historical_ratio: parseFloat(e.target.value),
            }))
          }
          className="w-full"
        />
        <p className="text-xs text-muted-foreground">{ld.historicalRatioHelp}</p>
      </div>
    </>
  );
}
