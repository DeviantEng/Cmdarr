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

export function LocalDiscoverySection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, plexAccounts, localDiscoveryUsedIds } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>Plex Account (play history source)</Label>
        <Select
          value={editForm.plex_history_account_id ?? ""}
          onValueChange={(v) =>
            setEditForm((f) => ({ ...f, plex_history_account_id: v }))
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select account" />
          </SelectTrigger>
          <SelectContent>
            {plexAccounts.map((acc) => (
              <SelectItem
                key={acc.id}
                value={acc.id}
                disabled={localDiscoveryUsedIds.has(acc.id)}
              >
                {acc.name || acc.id}
                {localDiscoveryUsedIds.has(acc.id)
                  ? " (already has Local Discovery)"
                  : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          Plex Home users only. Local Discovery uses this account&apos;s play
          history. One Local Discovery per user.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Lookback days</Label>
          <NumericInput
            value={editForm.lookback_days ?? 90}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, lookback_days: v ?? 90 }))
            }
            min={7}
            max={365}
            defaultValue={90}
          />
          <p className="text-xs text-muted-foreground">
            How far back to count plays. Shorter = more day-to-day variety. Min:
            7, max: 365.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Exclude played days</Label>
          <NumericInput
            value={editForm.exclude_played_days ?? 3}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, exclude_played_days: v ?? 3 }))
            }
            min={0}
            max={30}
            defaultValue={3}
          />
          <p className="text-xs text-muted-foreground">
            Skip tracks played in last N days. Reduces repetition. Min: 0, max:
            30.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Top artists count</Label>
          <NumericInput
            value={editForm.top_artists_count ?? 10}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, top_artists_count: v ?? 10 }))
            }
            min={1}
            max={20}
            defaultValue={10}
          />
          <p className="text-xs text-muted-foreground">
            How many top artists to randomly pick each run. Min: 1, max: 20.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Artist pool size</Label>
          <NumericInput
            value={editForm.artist_pool_size ?? 20}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, artist_pool_size: v ?? 20 }))
            }
            min={1}
            max={50}
            defaultValue={20}
          />
          <p className="text-xs text-muted-foreground">
            Size of artist pool to sample from (must be ≥ top artists count). Min:
            top artists, max: 50.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Max tracks</Label>
          <NumericInput
            value={editForm.max_tracks ?? 50}
            onChange={(v) => setEditForm((f) => ({ ...f, max_tracks: v ?? 50 }))}
            min={1}
            max={200}
            defaultValue={50}
          />
          <p className="text-xs text-muted-foreground">
            Target playlist size. Min: 1, max: 200.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Sonic similar limit</Label>
          <NumericInput
            value={editForm.sonic_similar_limit ?? 15}
            onChange={(v) =>
              setEditForm((f) => ({ ...f, sonic_similar_limit: v ?? 15 }))
            }
            min={5}
            max={50}
            defaultValue={15}
          />
          <p className="text-xs text-muted-foreground">
            Max sonically similar tracks per seed. Min: 5, max: 50.
          </p>
        </div>
        <div className="space-y-2">
          <Label>Sonic similarity distance</Label>
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
          <p className="text-xs text-muted-foreground">
            Plex sonic match threshold. Lower = stricter. Min: 0.1, max: 1.
          </p>
        </div>
      </div>
      <div className="space-y-2">
        <Label>Historical ratio: {editForm.historical_ratio ?? 0.4}</Label>
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
        <p className="text-xs text-muted-foreground">
          Share of tracks from play history vs sonically similar. 0.4 = 40%
          history, 60% similar.
        </p>
      </div>
  </>
    );
}
