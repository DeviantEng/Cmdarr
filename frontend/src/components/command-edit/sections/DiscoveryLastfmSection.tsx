import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";

export function DiscoveryLastfmSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-artists-to-query">Lidarr artists to sample</Label>
        <NumericInput
          id="edit-artists-to-query"
          value={editForm.artists_to_query ?? 3}
          onChange={(v) =>
            setEditForm((f) => ({ ...f, artists_to_query: v ?? 3 }))
          }
          min={1}
          max={100}
          defaultValue={3}
        />
        <p className="text-xs text-muted-foreground">
          Number of Lidarr artists to query Last.fm (1–100). Lower = faster.
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-artist-cooldown-days">Artist cooldown (days)</Label>
        <NumericInput
          id="edit-artist-cooldown-days"
          value={editForm.artist_cooldown_days ?? 30}
          onChange={(v) =>
            setEditForm((f) => ({ ...f, artist_cooldown_days: v ?? 30 }))
          }
          min={1}
          max={365}
          defaultValue={30}
        />
        <p className="text-xs text-muted-foreground">
          Don&apos;t re-query an artist for this many days (1–365, default 30)
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-similar-per-artist">Similar per artist</Label>
        <NumericInput
          id="edit-similar-per-artist"
          value={editForm.similar_per_artist ?? 1}
          onChange={(v) =>
            setEditForm((f) => ({ ...f, similar_per_artist: v ?? 1 }))
          }
          min={1}
          max={50}
          defaultValue={1}
        />
        <p className="text-xs text-muted-foreground">
          Similar artists to request per Lidarr artist (1–50)
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-lastfm-limit">Output limit</Label>
        <NumericInput
          id="edit-lastfm-limit"
          value={editForm.limit ?? 5}
          onChange={(v) => setEditForm((f) => ({ ...f, limit: v ?? 5 }))}
          min={1}
          max={50}
          defaultValue={5}
        />
        <p className="text-xs text-muted-foreground">
          Max artists in final output (1–50)
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-min-match-score">Min match score (0–1)</Label>
        <NumericInput
          id="edit-min-match-score"
          value={editForm.min_match_score ?? 0.9}
          onChange={(v) =>
            setEditForm((f) => ({ ...f, min_match_score: v ?? 0.9 }))
          }
          min={0}
          max={1}
          defaultValue={0.9}
          numericType="float"
        />
        <p className="text-xs text-muted-foreground">
          Minimum Last.fm match score (0–1, default 0.9)
        </p>
      </div>
  </>
    );
}
