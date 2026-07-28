import { api } from "@/lib/api";
import {
  NrdExclusionListDialog,
  type NrdExclusionListItem,
} from "@/components/NrdExclusionListDialog";

type LidarrWantedIgnoreDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

type IgnoreApiItem = {
  id: number;
  artist_name: string | null;
  album_title: string;
  album_type: string | null;
  release_date: string | null;
  ignored_at?: string | null;
  ignored_until: string | null;
  reason?: string | null;
  search_count: number;
};

function reasonLabel(reason: string | null | undefined): string | null {
  if (reason === "grabbed") return "grabbed";
  if (reason === "no_release_found") return "no release";
  return reason || null;
}

export function LidarrWantedIgnoreDialog({
  open,
  onOpenChange,
  onChanged,
}: LidarrWantedIgnoreDialogProps) {
  return (
    <NrdExclusionListDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Wanted Search ignore list"
      description="Albums temporarily skipped after a grab or when no release was found. They return when the cooldown ends, or restore them here (e.g. after fixing a failed import)."
      emptyMessage="No albums currently ignored."
      loadItems={async (): Promise<NrdExclusionListItem[]> => {
        const res = await api.request<{ total: number; items: IgnoreApiItem[] }>(
          "/api/lidarr-maintenance/ignore?active_only=true&limit=500"
        );
        return (res.items || []).map((item) => {
          const until = item.ignored_until
            ? new Date(item.ignored_until).toLocaleDateString()
            : null;
          const bits = [
            reasonLabel(item.reason),
            item.album_type || null,
            item.release_date || null,
            until ? `until ${until}` : null,
            item.search_count > 1 ? `searched ${item.search_count}×` : null,
          ].filter(Boolean);
          return {
            key: String(item.id),
            title: `${item.artist_name || "?"} – ${item.album_title}`,
            subtitle: bits.join(" · ") || undefined,
            addedAt: item.ignored_at ?? item.ignored_until,
          };
        });
      }}
      onRestore={async (key) => {
        await api.request(`/api/lidarr-maintenance/ignore/${key}`, { method: "DELETE" });
      }}
      onRestoreAll={async () => {
        const res = await api.request<{ deleted: number }>(
          "/api/lidarr-maintenance/ignore/restore-all",
          { method: "POST" }
        );
        return res.deleted ?? 0;
      }}
      restoreAllConfirmTitle="Clear ignore list?"
      restoreAllConfirmDescription={(count) =>
        `Restore all ${count} ignored album${count === 1 ? "" : "s"}? They may be searched again on the next Wanted Search run.`
      }
      onChanged={onChanged}
    />
  );
}
