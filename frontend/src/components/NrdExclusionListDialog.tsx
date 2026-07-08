import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RotateCcw, Search } from "lucide-react";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

export type NrdExclusionListItem = {
  key: string;
  title: string;
  subtitle?: string;
  addedAt?: string | null;
};

type SortMode = "name" | "date_desc" | "date_asc";

function formatAddedDate(value?: string | null): string | null {
  if (!value) return null;
  if (value.length >= 10 && value[4] === "-" && value[7] === "-") {
    return value.slice(0, 10);
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function sortItems(items: NrdExclusionListItem[], sort: SortMode): NrdExclusionListItem[] {
  const next = [...items];
  if (sort === "name") {
    next.sort((a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" }));
  } else if (sort === "date_desc") {
    next.sort((a, b) => (b.addedAt ?? "").localeCompare(a.addedAt ?? ""));
  } else {
    next.sort((a, b) => (a.addedAt ?? "").localeCompare(b.addedAt ?? ""));
  }
  return next;
}

type NrdExclusionListDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  emptyMessage: string;
  loadItems: () => Promise<NrdExclusionListItem[]>;
  onRestore: (key: string) => Promise<void>;
  onRestoreAll: () => Promise<number>;
  restoreAllConfirmTitle: string;
  restoreAllConfirmDescription: (count: number) => string;
  onChanged?: () => void;
};

export function NrdExclusionListDialog({
  open,
  onOpenChange,
  title,
  description,
  emptyMessage,
  loadItems,
  onRestore,
  onRestoreAll,
  restoreAllConfirmTitle,
  restoreAllConfirmDescription,
  onChanged,
}: NrdExclusionListDialogProps) {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<NrdExclusionListItem[]>([]);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortMode>("date_desc");
  const [confirmRestoreAll, setConfirmRestoreAll] = useState(false);
  const [restoreAllLoading, setRestoreAllLoading] = useState(false);
  const [restoringKey, setRestoringKey] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const loaded = await loadItems();
      setItems(loaded);
    } catch {
      toast.error(`Failed to load ${title.toLowerCase()}`);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [loadItems, title]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSort("date_desc");
    void refresh();
  }, [open, refresh]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = q
      ? items.filter((item) => {
          const haystack = `${item.title} ${item.subtitle ?? ""}`.toLowerCase();
          return haystack.includes(q);
        })
      : items;
    return sortItems(matched, sort);
  }, [items, query, sort]);

  const restoreOne = async (key: string) => {
    setRestoringKey(key);
    try {
      await onRestore(key);
      setItems((prev) => prev.filter((item) => item.key !== key));
      onChanged?.();
      toast.success("Restored");
    } catch {
      toast.error("Restore failed");
    } finally {
      setRestoringKey(null);
    }
  };

  const doRestoreAll = async () => {
    setRestoreAllLoading(true);
    try {
      const count = await onRestoreAll();
      setItems([]);
      setConfirmRestoreAll(false);
      onChanged?.();
      toast.success(
        count > 0 ? `Restored ${count} item${count === 1 ? "" : "s"}` : "Nothing to restore"
      );
    } catch {
      toast.error("Restore all failed");
    } finally {
      setRestoreAllLoading(false);
    }
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[80vh] max-w-2xl flex-col overflow-hidden">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search…"
                  className="h-9 pl-8"
                />
              </div>
              <Select value={sort} onValueChange={(v) => setSort(v as SortMode)}>
                <SelectTrigger className="h-9 w-full sm:w-[160px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="date_desc">Newest first</SelectItem>
                  <SelectItem value="date_asc">Oldest first</SelectItem>
                  <SelectItem value="name">Name A–Z</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmRestoreAll(true)}
                disabled={items.length === 0}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                Restore all
              </Button>
            </div>
          </div>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pt-1">
            {loading ? (
              <div className="flex justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : filtered.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {items.length === 0 ? emptyMessage : "No matches for your search."}
              </p>
            ) : (
              filtered.map((item) => {
                const added = formatAddedDate(item.addedAt);
                return (
                  <div
                    key={item.key}
                    className="flex flex-col gap-2 rounded-lg border px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-medium">{item.title}</div>
                      {item.subtitle ? (
                        <div className="truncate text-sm text-muted-foreground">
                          {item.subtitle}
                        </div>
                      ) : null}
                      {added ? (
                        <div className="mt-0.5 text-xs text-muted-foreground">Added {added}</div>
                      ) : null}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 self-start sm:self-auto"
                      disabled={restoringKey === item.key}
                      onClick={() => void restoreOne(item.key)}
                    >
                      {restoringKey === item.key ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      Restore
                    </Button>
                  </div>
                );
              })
            )}
          </div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog
        open={confirmRestoreAll}
        onOpenChange={setConfirmRestoreAll}
        title={restoreAllConfirmTitle}
        description={restoreAllConfirmDescription(items.length)}
        confirmLabel="Restore all"
        onConfirm={doRestoreAll}
        isLoading={restoreAllLoading}
      />
    </>
  );
}
