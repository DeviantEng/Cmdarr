import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { libraryAuditApi, type LibraryAuditFile } from "@/lib/library-audit-api";
import {
  LibraryAuditFileDetailDialog,
  LibraryAuditFileTable,
  LibraryAuditPagination,
} from "@/arr/pages/library-audit/library-audit-shared";
import { PAGE_SIZE } from "@/arr/pages/library-audit/library-audit-utils";

export function ArrLibraryAuditReviewPage() {
  const [files, setFiles] = useState<LibraryAuditFile[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

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

  return (
    <div>
      <ArrPageHeader
        title="Review"
        description="Files with warning or suspicious verdicts that still need a disposition."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void load(offset)}
            disabled={loading}
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
        <ArrPanelBody>
          <LibraryAuditFileTable
            files={files}
            loading={loading}
            emptyMessage="Nothing needs review right now."
            onSelect={(file) => {
              setSelectedId(file.id);
              setDetailOpen(true);
            }}
          />
          <LibraryAuditPagination
            total={total}
            offset={offset}
            limit={PAGE_SIZE}
            disabled={loading}
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
