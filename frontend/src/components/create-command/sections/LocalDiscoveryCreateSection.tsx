import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { ld } from "../shared";
import { NumericInput } from "@/components/NumericInput";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CreateCommandScheduleExpiryBlock } from "@/components/CreateCommandScheduleExpiryBlock";

export function LocalDiscoveryCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { plexAccounts, localDiscoveryUsedIds, localDiscoveryForm, setLocalDiscoveryForm } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{ld.plexAccountLabel}</Label>
        <Select
          value={localDiscoveryForm.plex_history_account_id}
          onValueChange={(v) =>
            setLocalDiscoveryForm((prev) => ({ ...prev, plex_history_account_id: v }))
          }
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
            value={localDiscoveryForm.lookback_days}
            onChange={(v) => setLocalDiscoveryForm((prev) => ({ ...prev, lookback_days: v ?? 90 }))}
            min={7}
            max={365}
            defaultValue={90}
          />
          <p className="text-xs text-muted-foreground">{ld.lookbackDaysHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.excludePlayedLabel}</Label>
          <NumericInput
            value={localDiscoveryForm.exclude_played_days}
            onChange={(v) =>
              setLocalDiscoveryForm((prev) => ({ ...prev, exclude_played_days: v ?? 3 }))
            }
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
            value={localDiscoveryForm.top_artists_count}
            onChange={(v) =>
              setLocalDiscoveryForm((prev) => ({
                ...prev,
                top_artists_count: v ?? 10,
              }))
            }
            min={1}
            max={20}
            defaultValue={10}
          />
          <p className="text-xs text-muted-foreground">{ld.topArtistsCountHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{ld.artistPoolSizeLabel}</Label>
          <NumericInput
            value={localDiscoveryForm.artist_pool_size}
            onChange={(v) =>
              setLocalDiscoveryForm((prev) => ({
                ...prev,
                artist_pool_size: v ?? 20,
              }))
            }
            min={1}
            max={50}
            defaultValue={20}
          />
          <p className="text-xs text-muted-foreground">{ld.artistPoolSizeHelp}</p>
        </div>
      </div>
      <div className="space-y-2">
        <Label>{ld.maxTracksLabel}</Label>
        <NumericInput
          value={localDiscoveryForm.max_tracks}
          onChange={(v) => setLocalDiscoveryForm((prev) => ({ ...prev, max_tracks: v ?? 50 }))}
          min={1}
          max={200}
          defaultValue={50}
        />
        <p className="text-xs text-muted-foreground">{ld.maxTracksHelp}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{ld.sonicSimilarLimitLabel}</Label>
          <NumericInput
            value={localDiscoveryForm.sonic_similar_limit}
            onChange={(v) =>
              setLocalDiscoveryForm((prev) => ({
                ...prev,
                sonic_similar_limit: v ?? 10,
              }))
            }
            min={5}
            max={50}
            defaultValue={15}
          />
          <p className="text-xs text-muted-foreground">{ld.sonicSimilarLimitHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>
            {ld.historicalRatioLabel} {localDiscoveryForm.historical_ratio}
          </Label>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={localDiscoveryForm.historical_ratio}
            onChange={(e) =>
              setLocalDiscoveryForm((prev) => ({
                ...prev,
                historical_ratio: parseFloat(e.target.value),
              }))
            }
            className="w-full"
          />
          <p className="text-xs text-muted-foreground">{ld.historicalRatioHelp}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{ld.sonicSimilarityDistanceLabel}</Label>
          <NumericInput
            value={localDiscoveryForm.sonic_similarity_distance}
            onChange={(v) =>
              setLocalDiscoveryForm((prev) => ({
                ...prev,
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
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-ld"
        scheduleOverride={localDiscoveryForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setLocalDiscoveryForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={localDiscoveryForm.schedule_cron}
        onScheduleCronChange={(v) =>
          setLocalDiscoveryForm((prev) => ({ ...prev, schedule_cron: v }))
        }
        enabled={localDiscoveryForm.enabled}
        onEnabledChange={(v) => setLocalDiscoveryForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={localDiscoveryForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setLocalDiscoveryForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={localDiscoveryForm.expires_at}
        onExpiresAtChange={(v) => setLocalDiscoveryForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={localDiscoveryForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setLocalDiscoveryForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
