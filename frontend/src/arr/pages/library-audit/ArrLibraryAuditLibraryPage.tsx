import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw, Search } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPageToolbar, ArrPanelBody } from "@/arr/components/ArrPageToolbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { libraryAuditApi, type LibraryAuditFile } from "@/lib/library-audit-api";
import {
  LibraryAuditFileDetailDialog,
  LibraryAuditFileTable,
  LibraryAuditPagination,
} from "@/arr/pages/library-audit/library-audit-shared";
import { PAGE_SIZE } from "@/arr/pages/library-audit/library-audit-utils";

const PRESENT_OPTIONS = [
  { value: "all", label: "Any presence" },
  { value: "true", label: "Present" },
  { value: "false", label: "Missing" },
] as const;

const ANALYSIS_STATE_OPTIONS = [
  { value: "all", label: "Any state" },
  { value: "PENDING", label: "Pending" },
  { value: "ANALYZING", label: "Analyzing" },
  { value: "ANALYZED", label: "Analyzed" },
  { value: "UNSUPPORTED", label: "Unsupported" },
  { value: "ERROR", label: "Error" },
  { value: "STALE", label: "Stale" },
] as const;

const VERDICT_OPTIONS = [
  { value: "all", label: "Any verdict" },
  { value: "AUTHENTIC", label: "Authentic" },
  { value: "WARNING", label: "Warning" },
  { value: "SUSPICIOUS", label: "Suspicious" },
  { value: "FAKE_CERTAIN", label: "Fake certain" },
  { value: "INCONCLUSIVE", label: "Inconclusive" },
  { value: "ERROR", label: "Error" },
] as const;

export function ArrLibraryAuditLibraryPage() {
  const [files, setFiles] = useState<LibraryAuditFile[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [present, setPresent] = useState<string>("all");
  const [analysisState, setAnalysisState] = useState<string>("all");
  const [verdict, setVerdict] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const load = useCallback(
    async (nextOffset: number) => {
      setLoading(true);
      try {
        const res = await libraryAuditApi.listFiles({
          limit: PAGE_SIZE,
          offset: nextOffset,
          q: q || undefined,
          present: present === "all" ? undefined : present === "true",
          analysis_state: analysisState === "all" ? undefined : analysisState,
          verdict: verdict === "all" ? undefined : verdict,
        });
        setFiles(res.items);
        setTotal(res.total);
        setOffset(res.offset);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Failed to load library files");
        setFiles([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [q, present, analysisState, verdict]
  );

  useEffect(() => {
    void load(0);
  }, [load]);

  const applySearch = () => {
    setQ(qInput.trim());
  };

  return (
    <div>
      <ArrPageHeader
        title="Library"
        description="Search and filter audited files across the music root."
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

      <div className="space-y-4">
        <ArrContentPanel>
          <ArrPageToolbar>
            <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-center">
              <div className="flex min-w-0 flex-1 gap-2">
                <Input
                  value={qInput}
                  onChange={(e) => setQInput(e.target.value)}
                  placeholder="Search path…"
                  className="min-w-0 flex-1"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") applySearch();
                  }}
                />
                <Button variant="secondary" size="sm" onClick={applySearch}>
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </Button>
              </div>
              <Select value={present} onValueChange={setPresent}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder="Presence" />
                </SelectTrigger>
                <SelectContent>
                  {PRESENT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={analysisState} onValueChange={setAnalysisState}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder="Analysis state" />
                </SelectTrigger>
                <SelectContent>
                  {ANALYSIS_STATE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={verdict} onValueChange={setVerdict}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder="Verdict" />
                </SelectTrigger>
                <SelectContent>
                  {VERDICT_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </ArrPageToolbar>
          <ArrPanelBody>
            <LibraryAuditFileTable
              files={files}
              loading={loading}
              emptyMessage="No files match these filters."
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
      </div>

      <LibraryAuditFileDetailDialog
        fileId={selectedId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onChanged={() => void load(offset)}
      />
    </div>
  );
}
