import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  libraryAuditApi,
  type LibraryAuditDisposition,
  type LibraryAuditFile,
} from "@/lib/library-audit-api";
import {
  LibraryAuditBulkBar,
  LibraryAuditFileDetailDialog,
  LibraryAuditFileTable,
  LibraryAuditPagination,
} from "@/arr/pages/library-audit/library-audit-shared";
import { formatDisposition, PAGE_SIZE } from "@/arr/pages/library-audit/library-audit-utils";

export function ArrLibraryAuditReviewPage() {
  const [files, setFiles] = useState<LibraryAuditFile[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectingFolderId, setSelectingFolderId] = useState<number | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = useCallback(async (nextOffset: number) => {
    setLoading(true);
    try {
      const res = await libraryAuditApi.listFiles({
        needs_review: true,
        limit: PAGE_SIZE,
        offset: nextOffset,
      });
      setFiles(res.items);
      setTotal(res.total);
      setOffset(res.offset);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load review queue");
      setFiles([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  const selectFolder = async (file: LibraryAuditFile) => {
    if (!file.parent_path) {
      toast.error("No folder path for this file");
      return;
    }
    setSelectingFolderId(file.id);
    try {
      const res = await libraryAuditApi.listFiles({
        needs_review: true,
        parent_path: file.parent_path,
        limit: 500,
        offset: 0,
      });
      const next = new Set(selectedIds);
      for (const item of res.items) next.add(item.id);
      setSelectedIds(next);
      toast.success(
        `Selected ${res.items.length.toLocaleString()} file${res.items.length === 1 ? "" : "s"} in ${file.parent_path}`
      );
      if (res.total > res.items.length) {
        toast(`Folder has ${res.total} matching files; selected first ${res.items.length}.`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to select folder");
    } finally {
      setSelectingFolderId(null);
    }
  };

  const runBulkDisposition = async (disposition: LibraryAuditDisposition) => {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    setBulkBusy(true);
    try {
      const res = await libraryAuditApi.bulkReview({ file_ids: ids, disposition });
      const errCount = res.errors?.length ?? 0;
      if (errCount) {
        toast.error(
          `Marked ${res.updated}; ${errCount} failed (${res.errors[0]?.error || "unknown error"})`
        );
      } else {
        toast.success(
          `Marked ${res.updated.toLocaleString()} as ${formatDisposition(disposition)}`
        );
      }
      setSelectedIds(new Set());
      await load(offset);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Bulk review failed");
    } finally {
      setBulkBusy(false);
    }
  };

  const runBulkReanalyze = async () => {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    setBulkBusy(true);
    try {
      const res = await libraryAuditApi.bulkReanalyze(ids);
      const errCount = res.errors?.length ?? 0;
      if (errCount) {
        toast.error(`Queued ${res.updated}; ${errCount} failed`);
      } else {
        toast.success(`Queued ${res.updated.toLocaleString()} for reanalysis`);
      }
      setSelectedIds(new Set());
      await load(offset);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Bulk reanalyze failed");
    } finally {
      setBulkBusy(false);
    }
  };

  return (
    <div>
      <ArrPageHeader
        title="Review"
        description="Files with warning or suspicious verdicts that still need a disposition. Select a folder to action a whole album at once."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void load(offset)}
            disabled={loading || bulkBusy}
          >
            {loading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Refresh
          </Button>
        }
      />

      <ArrContentPanel>
        <ArrSectionHeader
          title="Needs review"
          description={`${total.toLocaleString()} file${total === 1 ? "" : "s"} waiting for a decision.`}
        />
        <ArrPanelBody className="space-y-3">
          <LibraryAuditBulkBar
            selectedCount={selectedIds.size}
            busy={bulkBusy}
            onClear={() => setSelectedIds(new Set())}
            onDisposition={(d) => void runBulkDisposition(d)}
            onReanalyze={() => void runBulkReanalyze()}
          />
          <LibraryAuditFileTable
            files={files}
            loading={loading}
            emptyMessage="Nothing needs review right now."
            selectedIds={selectedIds}
            onSelectedIdsChange={setSelectedIds}
            onSelectFolder={(file) => void selectFolder(file)}
            selectingFolderId={selectingFolderId}
            onSelect={(file) => {
              setSelectedId(file.id);
              setDetailOpen(true);
            }}
          />
          <LibraryAuditPagination
            total={total}
            offset={offset}
            limit={PAGE_SIZE}
            disabled={loading || bulkBusy}
            onOffsetChange={(next) => void load(next)}
          />
        </ArrPanelBody>
      </ArrContentPanel>

      <LibraryAuditFileDetailDialog
        fileId={selectedId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onChanged={() => void load(offset)}
      />
    </div>
  );
}
