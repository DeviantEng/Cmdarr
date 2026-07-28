import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const lf = commandUiCopy.discoveryLastfm;

type Profile = { id: number; name: string };

export function DiscoveryLastfmSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  const [qualityProfiles, setQualityProfiles] = useState<Profile[]>([]);
  const [metadataProfiles, setMetadataProfiles] = useState<Profile[]>([]);
  const [loadingProfiles, setLoadingProfiles] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingProfiles(true);
      try {
        const res = await api.getLastfmDiscoveryLidarrProfiles();
        if (cancelled) return;
        setQualityProfiles(res.quality_profiles ?? []);
        setMetadataProfiles(res.metadata_profiles ?? []);
      } catch {
        if (!cancelled) {
          setQualityProfiles([]);
          setMetadataProfiles([]);
        }
      } finally {
        if (!cancelled) setLoadingProfiles(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="edit-artists-to-query">{lf.artistsToSample}</Label>
        <NumericInput
          id="edit-artists-to-query"
          value={editForm.artists_to_query ?? 3}
          onChange={(v) => setEditForm((f) => ({ ...f, artists_to_query: v ?? 3 }))}
          min={1}
          max={100}
          defaultValue={3}
        />
        <p className="text-xs text-muted-foreground">{lf.artistsToSampleHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-artist-cooldown-days">{lf.artistCooldown}</Label>
        <NumericInput
          id="edit-artist-cooldown-days"
          value={editForm.artist_cooldown_days ?? 30}
          onChange={(v) => setEditForm((f) => ({ ...f, artist_cooldown_days: v ?? 30 }))}
          min={1}
          max={365}
          defaultValue={30}
        />
        <p className="text-xs text-muted-foreground">{lf.artistCooldownHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-similar-per-artist">{lf.similarPerArtist}</Label>
        <NumericInput
          id="edit-similar-per-artist"
          value={editForm.similar_per_artist ?? 1}
          onChange={(v) => setEditForm((f) => ({ ...f, similar_per_artist: v ?? 1 }))}
          min={1}
          max={50}
          defaultValue={1}
        />
        <p className="text-xs text-muted-foreground">{lf.similarPerArtistHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-lastfm-limit">{lf.outputLimit}</Label>
        <NumericInput
          id="edit-lastfm-limit"
          value={editForm.limit ?? 5}
          onChange={(v) => setEditForm((f) => ({ ...f, limit: v ?? 5 }))}
          min={1}
          max={50}
          defaultValue={5}
        />
        <p className="text-xs text-muted-foreground">{lf.outputLimitHelp}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="edit-min-match-score">{lf.minMatchScore}</Label>
        <NumericInput
          id="edit-min-match-score"
          value={editForm.min_match_score ?? 0.9}
          onChange={(v) => setEditForm((f) => ({ ...f, min_match_score: v ?? 0.9 }))}
          min={0}
          max={1}
          defaultValue={0.9}
          numericType="float"
        />
        <p className="text-xs text-muted-foreground">{lf.minMatchScoreHelp}</p>
      </div>

      <div className="space-y-2">
        <Label>{lf.qualityProfile}</Label>
        <Select
          value={
            editForm.quality_profile_id != null && editForm.quality_profile_id > 0
              ? String(editForm.quality_profile_id)
              : ""
          }
          onValueChange={(v) =>
            setEditForm((f) => ({ ...f, quality_profile_id: Number(v) || null }))
          }
          disabled={loadingProfiles || qualityProfiles.length === 0}
        >
          <SelectTrigger>
            <SelectValue
              placeholder={loadingProfiles ? "Loading…" : lf.qualityProfilePlaceholder}
            />
          </SelectTrigger>
          <SelectContent>
            {qualityProfiles.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{lf.qualityProfileHelp}</p>
      </div>

      <div className="space-y-2">
        <Label>{lf.metadataProfile}</Label>
        <Select
          value={
            editForm.metadata_profile_id != null && editForm.metadata_profile_id > 0
              ? String(editForm.metadata_profile_id)
              : ""
          }
          onValueChange={(v) =>
            setEditForm((f) => ({ ...f, metadata_profile_id: Number(v) || null }))
          }
          disabled={loadingProfiles || metadataProfiles.length === 0}
        >
          <SelectTrigger>
            <SelectValue
              placeholder={loadingProfiles ? "Loading…" : lf.metadataProfilePlaceholder}
            />
          </SelectTrigger>
          <SelectContent>
            {metadataProfiles.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{lf.metadataProfileHelp}</p>
      </div>

      <div className="flex items-start gap-2 rounded-md border p-3">
        <input
          id="edit-search-for-missing-albums"
          type="checkbox"
          className="mt-1 h-4 w-4 accent-primary"
          checked={!!editForm.search_for_missing_albums}
          onChange={(e) =>
            setEditForm((f) => ({ ...f, search_for_missing_albums: e.target.checked }))
          }
        />
        <div className="space-y-1">
          <Label htmlFor="edit-search-for-missing-albums">{lf.searchOnAdd}</Label>
          <p className="text-xs text-muted-foreground">{lf.searchOnAddHelp}</p>
        </div>
      </div>
    </>
  );
}
