import { useCallback, useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  libraryAuditApi,
  type LibraryAuditDisposition,
  type LibraryAuditFile,
} from "@/lib/library-audit-api";
import {
  DISPOSITION_ACTIONS,
  formatDisposition,
  formatVerdict,
  verdictBadgeVariant,
} from "./library-audit-utils";

export function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border bg-background/50 px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function formatEvidence(evidence: unknown): string {
  if (evidence == null) return "No evidence recorded.";
  if (typeof evidence === "string") return evidence;
  try {
    return JSON.stringify(evidence, null, 2);
  } catch {
    return String(evidence);
  }
}

type LibraryAuditFileDetailDialogProps = {
  fileId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onChanged?: () => void;
};

export function LibraryAuditFileDetailDialog({
  fileId,
  open,
  onOpenChange,
  onChanged,
}: LibraryAuditFileDetailDialogProps) {
  const [file, setFile] = useState<LibraryAuditFile | null>(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState<
    LibraryAuditDisposition | "reanalyze" | "reset" | null
  >(null);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    try {
      const next = await libraryAuditApi.getFile(id);
      setFile(next);
      setNote(next.review?.note ?? "");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load file");
      setFile(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open || fileId == null) {
      setFile(null);
      setNote("");
      return;
    }
    void load(fileId);
  }, [open, fileId, load]);

  const handleReview = async (disposition: LibraryAuditDisposition) => {
    if (fileId == null) return;
    setSubmitting(disposition);
    try {
      await libraryAuditApi.submitReview(fileId, {
        disposition,
        note: note.trim() || undefined,
      });
      toast.success(`Marked as ${formatDisposition(disposition)}`);
      onChanged?.();
      onOpenChange(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save review");
    } finally {
      setSubmitting(null);
    }
  };

  const handleReanalyze = async () => {
    if (fileId == null) return;
    setSubmitting("reanalyze");
    try {
      const next = await libraryAuditApi.reanalyze(fileId);
      setFile(next);
      setNote(next.review?.note ?? "");
      const verdict = next.analysis?.verdict;
      toast.success(
        verdict ? `Reanalysis complete: ${formatVerdict(verdict)}` : "Reanalysis complete"
      );
      onChanged?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reanalysis failed");
    } finally {
      setSubmitting(null);
    }
  };

  const handleResetDisposition = async () => {
    if (fileId == null) return;
    setSubmitting("reset");
    try {
      const next = await libraryAuditApi.clearReview(fileId);
      setFile(next);
      setNote("");
      toast.success("Disposition cleared");
      onChanged?.();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to reset disposition");
    } finally {
      setSubmitting(null);
    }
  };

  const analysis = file?.analysis;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate pr-6">
            {file?.file_name || (loading ? "Loading…" : "File detail")}
          </DialogTitle>
          <DialogDescription className="break-all font-mono text-xs">
            {file?.relative_path || "—"}
          </DialogDescription>
        </DialogHeader>

        {loading && !file ? (
          <div className="flex min-h-[120px] items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : file ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={verdictBadgeVariant(analysis?.verdict)}>
                {formatVerdict(analysis?.verdict)}
              </Badge>
              {analysis?.score != null ? (
                <Badge variant="outline">Score {analysis.score}</Badge>
              ) : null}
              {file.review?.disposition ? (
                <Badge variant="secondary">{formatDisposition(file.review.disposition)}</Badge>
              ) : (
                <Badge variant="outline">Needs review</Badge>
              )}
              <Badge variant={file.is_present ? "default" : "secondary"}>
                {file.is_present ? "Present" : "Missing"}
              </Badge>
              <Badge variant="outline">{file.analysis_state}</Badge>
            </div>

            {analysis?.summary ? (
              <p className="text-sm leading-relaxed text-foreground">{analysis.summary}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No analysis summary available.</p>
            )}

            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">Evidence</div>
              <pre className="max-h-48 overflow-auto rounded-md border border-border bg-background/50 p-3 text-xs leading-relaxed">
                {formatEvidence(analysis?.evidence)}
              </pre>
            </div>

            {(file.artist || file.album || file.title) && (
              <div className="grid gap-2 text-sm sm:grid-cols-3">
                <div>
                  <div className="text-xs text-muted-foreground">Artist</div>
                  <div>{file.artist || "—"}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Album</div>
                  <div>{file.album || "—"}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Title</div>
                  <div>{file.title || "—"}</div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="library-audit-note">Note</Label>
              <Textarea
                id="library-audit-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Optional review note"
                rows={3}
              />
            </div>

            <div className="flex flex-wrap gap-2">
              {DISPOSITION_ACTIONS.map((action) => (
                <Button
                  key={action.value}
                  size="sm"
                  variant={action.value === "REPLACE" ? "destructive" : "secondary"}
                  disabled={submitting != null}
                  onClick={() => void handleReview(action.value)}
                >
                  {submitting === action.value ? (
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  {action.label}
                </Button>
              ))}
              {file.review?.disposition ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={submitting != null}
                  onClick={() => void handleResetDisposition()}
                >
                  {submitting === "reset" ? (
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                  ) : null}
                  Reset disposition
                </Button>
              ) : null}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">File not found.</p>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button
            variant="outline"
            size="sm"
            disabled={fileId == null || submitting != null}
            onClick={() => void handleReanalyze()}
          >
            {submitting === "reanalyze" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-2 h-4 w-4" />
            )}
            Reanalyze
          </Button>
          <Button variant="secondary" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type PaginationProps = {
  total: number;
  offset: number;
  limit: number;
  onOffsetChange: (offset: number) => void;
  disabled?: boolean;
};

export function LibraryAuditPagination({
  total,
  offset,
  limit,
  onOffsetChange,
  disabled,
}: PaginationProps) {
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 pt-3 text-sm text-muted-foreground">
      <span>{total === 0 ? "No results" : `${start}–${end} of ${total.toLocaleString()}`}</span>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled || !canPrev}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          Previous
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled || !canNext}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}

type FileTableProps = {
  files: LibraryAuditFile[];
  loading: boolean;
  onSelect: (file: LibraryAuditFile) => void;
  emptyMessage: string;
};

export function LibraryAuditFileTable({ files, loading, onSelect, emptyMessage }: FileTableProps) {
  if (loading && files.length === 0) {
    return (
      <div className="flex min-h-[120px] items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!files.length) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="arr-table w-full">
        <thead className="border-b">
          <tr>
            <th className="px-3 py-2 text-left text-sm font-medium">Path</th>
            <th className="px-3 py-2 text-left text-sm font-medium">Verdict</th>
            <th className="px-3 py-2 text-left text-sm font-medium">Score</th>
            <th className="px-3 py-2 text-left text-sm font-medium">State</th>
            <th className="px-3 py-2 text-left text-sm font-medium">Disposition</th>
          </tr>
        </thead>
        <tbody>
          {files.map((file) => (
            <tr
              key={file.id}
              className={cn(
                "cursor-pointer border-b last:border-b-0 hover:bg-muted/30",
                loading && "opacity-70"
              )}
              onClick={() => onSelect(file)}
            >
              <td
                className="max-w-[28rem] truncate px-3 py-2 font-mono text-xs"
                title={file.relative_path}
              >
                {file.relative_path}
              </td>
              <td className="px-3 py-2">
                <Badge
                  variant={verdictBadgeVariant(file.analysis?.verdict)}
                  className="text-[10px]"
                >
                  {formatVerdict(file.analysis?.verdict)}
                </Badge>
              </td>
              <td className="px-3 py-2 tabular-nums text-muted-foreground">
                {file.analysis?.score ?? "—"}
              </td>
              <td className="px-3 py-2 text-muted-foreground">{file.analysis_state}</td>
              <td className="px-3 py-2 text-muted-foreground">
                {formatDisposition(file.review?.disposition)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
