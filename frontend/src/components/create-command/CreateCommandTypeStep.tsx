import type { CreateCommandWizard } from "./useCreateCommandWizard";
import { cw, typePickerIconClass } from "./shared";
import { cn } from "@/lib/utils";
import {
  Music,
  Globe,
  Sun,
  ListMusic,
  Compass,
  Sparkles,
  Radio,
  Users,
  Mic2,
  RefreshCw,
  Search,
  Info,
} from "lucide-react";

export function CreateCommandTypeStep({ wizard }: { wizard: CreateCommandWizard }) {
  const { embedded, handleSelectType, singletonCardProps } = wizard;
  return (
    <div className={embedded ? "arr-panel-body arr-create-type-grid px-4 py-4" : "grid gap-3 py-4"}>
      <div
        className={
          embedded
            ? "arr-create-type-category"
            : "col-span-full text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        }
      >
        {cw.categoryPlaylistGenerator}
      </div>
      {/* Daylist */}
      {(() => {
        const { blocked, reason } = singletonCardProps("daylist");
        return (
          <button
            type="button"
            disabled={blocked}
            onClick={() => handleSelectType("daylist")}
            title={blocked ? reason : undefined}
            className={cn(
              embedded
                ? "arr-create-type-card"
                : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent",
              blocked && "cursor-not-allowed opacity-50 hover:border-border hover:bg-transparent"
            )}
          >
            <div className={typePickerIconClass(embedded, "bg-amber-100 dark:bg-amber-900")}>
              <Sun className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
                {cw.cardDaylistTitle}
              </h3>
              <p className="text-xs text-muted-foreground">{cw.cardDaylistBlurb}</p>
            </div>
            {blocked ? (
              <span className="shrink-0 text-muted-foreground" title={reason} aria-label={reason}>
                <Info className="h-4 w-4" />
              </span>
            ) : null}
          </button>
        );
      })()}

      {/* Local Discovery */}
      {(() => {
        const { blocked, reason } = singletonCardProps("local_discovery");
        return (
          <button
            type="button"
            disabled={blocked}
            onClick={() => handleSelectType("local_discovery")}
            title={blocked ? reason : undefined}
            className={cn(
              embedded
                ? "arr-create-type-card"
                : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent",
              blocked && "cursor-not-allowed opacity-50 hover:border-border hover:bg-transparent"
            )}
          >
            <div className={typePickerIconClass(embedded, "bg-teal-100 dark:bg-teal-900")}>
              <Compass className="h-5 w-5 text-teal-600 dark:text-teal-400" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
                {cw.cardLocalDiscoveryTitle}
              </h3>
              <p className="text-xs text-muted-foreground">{cw.cardLocalDiscoveryBlurb}</p>
            </div>
            {blocked ? (
              <span className="shrink-0 text-muted-foreground" title={reason} aria-label={reason}>
                <Info className="h-4 w-4" />
              </span>
            ) : null}
          </button>
        );
      })()}

      {/* Top Tracks / Artist Essentials */}
      <button
        onClick={() => handleSelectType("top_tracks")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-blue-100 dark:bg-blue-900")}>
          <ListMusic className="h-5 w-5 text-blue-600 dark:text-blue-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardArtistEssentialsTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardArtistEssentialsBlurb}</p>
        </div>
      </button>

      {/* Last.fm Similar */}
      <button
        onClick={() => handleSelectType("lfm_similar")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-indigo-100 dark:bg-indigo-900")}>
          <Users className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardLfmSimilarTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardLfmSimilarBlurb}</p>
        </div>
      </button>

      {/* Setlist.fm */}
      <button
        onClick={() => handleSelectType("setlistfm")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-rose-100 dark:bg-rose-900")}>
          <Mic2 className="h-5 w-5 text-rose-600 dark:text-rose-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardSetlistFmTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardSetlistFmBlurb}</p>
        </div>
      </button>

      {/* XMPlaylist (SiriusXM History) */}
      <button
        onClick={() => handleSelectType("xmplaylist")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-sky-100 dark:bg-sky-900")}>
          <Radio className="h-5 w-5 text-sky-600 dark:text-sky-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardXmplaylistTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardXmplaylistBlurb}</p>
        </div>
      </button>

      {/* Mood Playlist */}
      <button
        onClick={() => handleSelectType("mood_playlist")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-violet-100 dark:bg-violet-900")}>
          <Sparkles className="h-5 w-5 text-violet-600 dark:text-violet-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardMoodTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardMoodBlurb}</p>
        </div>
      </button>

      <div
        className={
          embedded
            ? "arr-create-type-category"
            : "col-span-full mt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        }
      >
        {cw.categoryPlaylistSync}
      </div>

      {/* ListenBrainz Curated */}
      <button
        onClick={() => handleSelectType("listenbrainz")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-purple-100 dark:bg-purple-900")}>
          <Music className="h-5 w-5 text-purple-600 dark:text-purple-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardListenbrainzTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardListenbrainzBlurb}</p>
        </div>
      </button>

      {/* External Playlist */}
      <button
        onClick={() => handleSelectType("other")}
        className={
          embedded
            ? "arr-create-type-card"
            : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent"
        }
      >
        <div className={typePickerIconClass(embedded, "bg-green-100 dark:bg-green-900")}>
          <Globe className="h-5 w-5 text-green-600 dark:text-green-400" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
            {cw.cardExternalTitle}
          </h3>
          <p className="text-xs text-muted-foreground">{cw.cardExternalBlurb}</p>
        </div>
      </button>

      <div
        className={
          embedded
            ? "arr-create-type-category"
            : "col-span-full mt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
        }
      >
        {cw.categoryLidarrMaintenance}
      </div>

      {/* Lidarr Update All */}
      {(() => {
        const { blocked, reason } = singletonCardProps("lidarr_update_all");
        return (
          <button
            type="button"
            disabled={blocked}
            onClick={() => handleSelectType("lidarr_update_all")}
            title={blocked ? reason : undefined}
            className={cn(
              embedded
                ? "arr-create-type-card"
                : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent",
              blocked && "cursor-not-allowed opacity-50 hover:border-border hover:bg-transparent"
            )}
          >
            <div className={typePickerIconClass(embedded, "bg-orange-100 dark:bg-orange-900")}>
              <RefreshCw className="h-5 w-5 text-orange-600 dark:text-orange-400" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
                {cw.cardLidarrUpdateAllTitle}
              </h3>
              <p className="text-xs text-muted-foreground">{cw.cardLidarrUpdateAllBlurb}</p>
            </div>
            {blocked ? (
              <span className="shrink-0 text-muted-foreground" title={reason} aria-label={reason}>
                <Info className="h-4 w-4" />
              </span>
            ) : null}
          </button>
        );
      })()}

      {/* Lidarr Wanted Search */}
      {(() => {
        const { blocked, reason } = singletonCardProps("lidarr_wanted_search");
        return (
          <button
            type="button"
            disabled={blocked}
            onClick={() => handleSelectType("lidarr_wanted_search")}
            title={blocked ? reason : undefined}
            className={cn(
              embedded
                ? "arr-create-type-card"
                : "flex items-center gap-3 rounded-lg border-2 border-border p-3 text-left transition-colors hover:border-primary hover:bg-accent",
              blocked && "cursor-not-allowed opacity-50 hover:border-border hover:bg-transparent"
            )}
          >
            <div className={typePickerIconClass(embedded, "bg-cyan-100 dark:bg-cyan-900")}>
              <Search className="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className={embedded ? "text-sm font-medium leading-snug" : "font-semibold"}>
                {cw.cardLidarrWantedSearchTitle}
              </h3>
              <p className="text-xs text-muted-foreground">{cw.cardLidarrWantedSearchBlurb}</p>
            </div>
            {blocked ? (
              <span className="shrink-0 text-muted-foreground" title={reason} aria-label={reason}>
                <Info className="h-4 w-4" />
              </span>
            ) : null}
          </button>
        );
      })()}
    </div>
  );
}
