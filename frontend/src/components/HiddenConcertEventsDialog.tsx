import { api } from "@/lib/api";
import {
  NrdExclusionListDialog,
  type NrdExclusionListItem,
} from "@/components/NrdExclusionListDialog";

type HiddenConcertEventsDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

export function HiddenConcertEventsDialog({
  open,
  onOpenChange,
  onChanged,
}: HiddenConcertEventsDialogProps) {
  return (
    <NrdExclusionListDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Hidden events"
      description="Individual shows hidden from the upcoming list. Restore to show them again."
      emptyMessage="No hidden events."
      loadItems={async (): Promise<NrdExclusionListItem[]> => {
        const res = await api.getHiddenEvents(500);
        return res.items.map((item) => {
          const venue = [item.venue_name, item.venue_city].filter(Boolean).join(" · ");
          const subtitle = venue ? `${venue} · ${item.local_date}` : item.local_date;
          return {
            key: String(item.event_id),
            title: item.artist_name,
            subtitle,
            addedAt: item.hidden_at,
          };
        });
      }}
      onRestore={async (key) => {
        await api.unhideEventRow(Number(key));
      }}
      onRestoreAll={async () => {
        const res = await api.unhideAllHiddenEvents();
        return res.removed ?? 0;
      }}
      restoreAllConfirmTitle="Restore all hidden events?"
      restoreAllConfirmDescription={(count) =>
        `Restore all ${count} hidden event${count === 1 ? "" : "s"}? Those shows will appear in the list again.`
      }
      onChanged={onChanged}
    />
  );
}
