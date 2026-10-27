import type { CreateCommandWizard } from "../useCreateCommandWizard";
import { lf } from "../shared";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

export function LfmSimilarCreateSection({ wizard }: { wizard: CreateCommandWizard }) {
  const { lfmSimilarForm, setLfmSimilarForm } = wizard;
  return (
    <>
      <div className="space-y-2">
        <Label>{lf.seedArtistsLabel}</Label>
        <Textarea
          className="min-h-[120px]"
          placeholder={lf.seedArtistsPlaceholder}
          value={lfmSimilarForm.seed_artists}
          onChange={(e) => setLfmSimilarForm((prev) => ({ ...prev, seed_artists: e.target.value }))}
        />
        <p className="text-xs text-muted-foreground">{lf.seedArtistsHelp}</p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>{lf.similarPerSeedLabel}</Label>
          <NumericInput
            placeholder="5"
            value={lfmSimilarForm.similar_per_seed}
            onChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, similar_per_seed: v ?? 5 }))}
            min={1}
            max={50}
            defaultValue={5}
          />
          <p className="text-xs text-muted-foreground">{lf.similarPerSeedHelp}</p>
        </div>
        <div className="space-y-2">
          <Label>{lf.maxArtistsLabel}</Label>
          <NumericInput
            placeholder="25"
            value={lfmSimilarForm.max_artists}
            onChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, max_artists: v ?? 25 }))}
            min={1}
            max={200}
            defaultValue={25}
          />
          <p className="text-xs text-muted-foreground">{lf.maxArtistsHelp}</p>
        </div>
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={lfmSimilarForm.include_seeds}
          onChange={(e) =>
            setLfmSimilarForm((prev) => ({ ...prev, include_seeds: e.target.checked }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{lf.includeSeedsLabel}</span>
      </label>
      <p className="text-xs text-muted-foreground">{lf.includeSeedsHelp}</p>
      <div className="space-y-2">
        <Label>{lf.topXLabel}</Label>
        <NumericInput
          placeholder="5"
          value={lfmSimilarForm.top_x}
          onChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, top_x: v ?? 5 }))}
          min={1}
          max={20}
          defaultValue={5}
        />
        <p className="text-xs text-muted-foreground">{lf.topXHelp}</p>
      </div>
      <div className="space-y-2">
        <Label>{lf.targetLabel}</Label>
        <Select
          value={lfmSimilarForm.target}
          onValueChange={(v: "plex" | "jellyfin") =>
            setLfmSimilarForm((prev) => ({ ...prev, target: v }))
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="plex">Plex</SelectItem>
            <SelectItem value="jellyfin">Jellyfin</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">{lf.targetWhereHelp}</p>
      </div>
      <p className="text-xs text-muted-foreground">{lf.lastfmNote}</p>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          checked={lfmSimilarForm.use_custom_playlist_name}
          onChange={(e) =>
            setLfmSimilarForm((prev) => ({
              ...prev,
              use_custom_playlist_name: e.target.checked,
            }))
          }
          className="rounded border-input"
        />
        <span className="text-sm">{lf.useCustomPlaylistName}</span>
      </label>
      {lfmSimilarForm.use_custom_playlist_name && (
        <div className="space-y-2">
          <Label>{lf.customPlaylistNameLabel}</Label>
          <Input
            value={lfmSimilarForm.custom_playlist_name}
            onChange={(e) =>
              setLfmSimilarForm((prev) => ({
                ...prev,
                custom_playlist_name: e.target.value,
              }))
            }
            placeholder={lf.customPlaylistPlaceholder}
          />
          <p className="text-xs text-muted-foreground">{lf.customPlaylistNameHelper}</p>
        </div>
      )}
      {!lfmSimilarForm.use_custom_playlist_name && (
        <p className="text-xs text-muted-foreground">{lf.autoNameHelp}</p>
      )}
      <CreateCommandScheduleExpiryBlock
        idPrefix="create-lf"
        scheduleOverride={lfmSimilarForm.schedule_override}
        onScheduleOverrideChange={(v) =>
          setLfmSimilarForm((prev) => ({ ...prev, schedule_override: v }))
        }
        scheduleCron={lfmSimilarForm.schedule_cron}
        onScheduleCronChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, schedule_cron: v }))}
        enabled={lfmSimilarForm.enabled}
        onEnabledChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, enabled: v }))}
        expiresAtEnabled={lfmSimilarForm.expires_at_enabled}
        onExpiresAtEnabledChange={(v) =>
          setLfmSimilarForm((prev) => ({
            ...prev,
            expires_at_enabled: v,
            expires_at: v && !prev.expires_at ? "" : prev.expires_at,
          }))
        }
        expiresAt={lfmSimilarForm.expires_at}
        onExpiresAtChange={(v) => setLfmSimilarForm((prev) => ({ ...prev, expires_at: v }))}
        expiresAtDeletePlaylist={lfmSimilarForm.expires_at_delete_playlist ?? true}
        onExpiresAtDeletePlaylistChange={(v) =>
          setLfmSimilarForm((prev) => ({ ...prev, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
