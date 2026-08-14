import { Fragment, useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Loader2, RefreshCw } from "lucide-react";
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
  type LibraryAuditFileSortBy,
  type LibraryAuditSortDir,
} from "@/lib/library-audit-api";
import {
  DISPOSITION_ACTIONS,
  formatDisposition,
  formatVerdict,
  verdictBadgeVariant,
} from "./library-audit-utils";
import { LibraryAuditSpectrumPanel } from "./library-audit-spectrum";

function asEvidenceRecord(evidence: unknown): Record<string, unknown> | null {
  if (evidence && typeof evidence === "object" && !Array.isArray(evidence)) {
    return evidence as Record<string, unknown>;
  }
  return null;
}

function formatHz(value: unknown): string | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return null;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 1 : 2)} kHz`;
  return `${Math.round(n)} Hz`;
}

function formatKbps(value: unknown): string | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) return null;
  return `${Math.round(n)} kbps`;
}

function formatEvidence(evidence: unknown): string {
  if (evidence == null) return "No evidence recorded.";
  if (typeof evidence === "string") return evidence;
  try {
    // Omit bulky spectrum curve from the raw evidence dump (shown in Spectrum panel).
    if (evidence && typeof evidence === "object" && "spectrum_curve" in evidence) {
      const rest = { ...(evidence as Record<string, unknown>) };
      delete rest.spectrum_curve;
      return JSON.stringify(rest, null, 2);
    }
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
    const wasPendingDeep = file?.analysis_state === "PENDING_DEEP";
    setSubmitting("reanalyze");
    try {
      const next = await libraryAuditApi.reanalyze(fileId);
      setFile(next);
      setNote(next.review?.note ?? "");
      const verdict = next.analysis?.verdict;
      toast.success(
        verdict
          ? `${wasPendingDeep ? "Deep scan" : "Reanalysis"} complete: ${formatVerdict(verdict)}`
          : wasPendingDeep
            ? "Deep scan complete"
            : "Reanalysis complete"
      );
      onChanged?.();
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : wasPendingDeep ? "Deep scan failed" : "Reanalysis failed"
      );
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
  const evidence = asEvidenceRecord(analysis?.evidence);
  const cutoffLabel = formatHz(analysis?.cutoff_hz ?? evidence?.cutoff_freq);
  const estimatedBitrate = formatKbps(evidence?.estimated_mp3_bitrate ?? evidence?.bitrate_kbps);
  const containerBitrate = formatKbps(evidence?.container_bitrate_kbps);
  const analysisPass = typeof evidence?.analysis_pass === "string" ? evidence.analysis_pass : null;
  const integrity = asEvidenceRecord(evidence?.integrity);
  const pendingDeep = file?.analysis_state === "PENDING_DEEP";
  const triageVerdict =
    typeof evidence?.triage_verdict === "string" ? evidence.triage_verdict : null;

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
              ) : pendingDeep ? (
                <Badge variant="secondary">Awaiting deep scan</Badge>
              ) : (
                <Badge variant="outline">Needs review</Badge>
              )}
              <Badge variant={file.is_present ? "default" : "secondary"}>
                {file.is_present ? "Present" : "Missing"}
              </Badge>
              {!pendingDeep ? <Badge variant="outline">{file.analysis_state}</Badge> : null}
              {pendingDeep ? (
                <Badge variant="outline">
                  Last pass: triage
                  {triageVerdict ? ` (${formatVerdict(triageVerdict)})` : ""}
                </Badge>
              ) : analysisPass ? (
                <Badge variant="outline">Last pass: {analysisPass}</Badge>
              ) : null}
            </div>

            {pendingDeep ? (
              <p className="text-sm text-muted-foreground">
                Quick triage flagged this file. A deeper scan is queued for a later command run, or
                run <span className="font-medium text-foreground">Deep scan</span> now to confirm
                the result immediately.
              </p>
            ) : null}

            {(cutoffLabel || estimatedBitrate || containerBitrate) && (
              <div className="flex flex-wrap gap-2">
                {cutoffLabel ? <Badge variant="secondary">Cutoff {cutoffLabel}</Badge> : null}
                {estimatedBitrate ? (
                  <Badge variant="secondary">Est. {estimatedBitrate}</Badge>
                ) : null}
                {containerBitrate ? (
                  <Badge variant="secondary">Container {containerBitrate}</Badge>
                ) : null}
              </div>
            )}

            {integrity?.duration_mismatch || integrity?.is_corrupted ? (
              <p className="text-xs text-destructive">
                Integrity:
                {integrity.is_corrupted ? " corrupted" : ""}
                {integrity.duration_mismatch ? " duration mismatch" : ""}
              </p>
            ) : null}

            {analysis?.verdict_overridden && analysis.scan_verdict ? (
              <p className="text-xs text-muted-foreground">
                Scanner reported {formatVerdict(analysis.scan_verdict)}; marked false positive so
                this file is treated as authentic.
              </p>
            ) : null}

            {analysis?.summary ? (
              <p className="text-sm leading-relaxed text-foreground">{analysis.summary}</p>
            ) : (
              <p className="text-sm text-muted-foreground">No analysis summary available.</p>
            )}

            <LibraryAuditSpectrumPanel
              fileId={fileId}
              open={open}
              extension={file.extension}
              isPresent={file.is_present}
              evidence={analysis?.evidence}
            />

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
          <div className="flex flex-wrap gap-2">
            {pendingDeep ? (
              <Button
                variant="default"
                size="sm"
                disabled={fileId == null || submitting != null}
                onClick={() => void handleReanalyze()}
              >
                {submitting === "reanalyze" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Deep scan
              </Button>
            ) : (
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
            )}
          </div>
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
  selectedIds?: Set<number>;
  onSelectedIdsChange?: (next: Set<number>) => void;
  onSelectFolder?: (file: LibraryAuditFile) => void;
  selectingFolderId?: number | null;
  sortBy?: LibraryAuditFileSortBy;
  sortDir?: LibraryAuditSortDir;
  onSortChange?: (sortBy: LibraryAuditFileSortBy, sortDir: LibraryAuditSortDir) => void;
};

const DEFAULT_SORT_DIR: Record<LibraryAuditFileSortBy, LibraryAuditSortDir> = {
  path: "asc",
  verdict: "asc",
  score: "desc",
  state: "asc",
  disposition: "asc",
  folder_pending_deep: "desc",
};

function SortableTh({
  label,
  column,
  sortBy,
  sortDir,
  onSortChange,
  className,
  title,
}: {
  label: string;
  column: LibraryAuditFileSortBy;
  sortBy?: LibraryAuditFileSortBy;
  sortDir?: LibraryAuditSortDir;
  onSortChange?: (sortBy: LibraryAuditFileSortBy, sortDir: LibraryAuditSortDir) => void;
  className?: string;
  title?: string;
}) {
  if (!onSortChange) {
    return <th className={cn("px-3 py-2 text-left text-sm font-medium", className)}>{label}</th>;
  }
  const active = sortBy === column;
  const Icon = !active ? ArrowUpDown : sortDir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className={cn("px-3 py-2 text-left text-sm font-medium", className)}>
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-1 rounded-sm hover:text-foreground",
          active ? "text-foreground" : "text-muted-foreground"
        )}
        title={title || `Sort by ${label}`}
        onClick={() => {
          if (active) {
            onSortChange(column, sortDir === "asc" ? "desc" : "asc");
          } else {
            onSortChange(column, DEFAULT_SORT_DIR[column]);
          }
        }}
      >
        {label}
        <Icon className="h-3.5 w-3.5 opacity-70" aria-hidden />
      </button>
    </th>
  );
}

export function LibraryAuditFileTable({
  files,
  loading,
  onSelect,
  emptyMessage,
  selectedIds,
  onSelectedIdsChange,
  onSelectFolder,
  selectingFolderId,
  sortBy,
  sortDir,
  onSortChange,
}: FileTableProps) {
  const selectable = Boolean(selectedIds && onSelectedIdsChange);
  const pageIds = files.map((f) => f.id);
  const allSelected =
    selectable && pageIds.length > 0 && pageIds.every((id) => selectedIds!.has(id));
  const someSelected = selectable && !allSelected && pageIds.some((id) => selectedIds!.has(id));

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

  const toggleOne = (id: number, checked: boolean) => {
    if (!onSelectedIdsChange || !selectedIds) return;
    const next = new Set(selectedIds);
    if (checked) next.add(id);
    else next.delete(id);
    onSelectedIdsChange(next);
  };

  const togglePage = (checked: boolean) => {
    if (!onSelectedIdsChange || !selectedIds) return;
    const next = new Set(selectedIds);
    for (const id of pageIds) {
      if (checked) next.add(id);
      else next.delete(id);
    }
    onSelectedIdsChange(next);
  };

  const colSpan = 5 + (selectable ? 1 : 0) + (onSelectFolder ? 1 : 0);

  // Group consecutive files by parent_path (API sorts keep folders together for path /
  // folder_pending_deep; other sorts may split a folder across multiple headers).
  const groups: { folder: string; files: LibraryAuditFile[] }[] = [];
  for (const file of files) {
    const folder = file.parent_path || "(root)";
    const last = groups[groups.length - 1];
    if (last && last.folder === folder) last.files.push(file);
    else groups.push({ folder, files: [file] });
  }

  return (
    <div className="overflow-x-auto">
      <table className="arr-table w-full">
        <thead className="border-b">
          <tr>
            {selectable ? (
              <th className="w-10 px-3 py-2 text-left">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={allSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = someSelected;
                  }}
                  onChange={(e) => togglePage(e.target.checked)}
                  aria-label="Select all on page"
                />
              </th>
            ) : null}
            <SortableTh
              label="Path"
              column="path"
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={onSortChange}
            />
            <SortableTh
              label="Verdict"
              column="verdict"
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={onSortChange}
            />
            <SortableTh
              label="Score"
              column="score"
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={onSortChange}
            />
            <SortableTh
              label="State"
              column="state"
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={onSortChange}
            />
            <SortableTh
              label="Disposition"
              column="disposition"
              sortBy={sortBy}
              sortDir={sortDir}
              onSortChange={onSortChange}
            />
            {onSelectFolder ? (
              <SortableTh
                label="Folder"
                column="folder_pending_deep"
                sortBy={sortBy}
                sortDir={sortDir}
                onSortChange={onSortChange}
                title="Sort by pending deep count in folder"
              />
            ) : null}
          </tr>
        </thead>
        <tbody>
          {groups.map((group, groupIndex) => {
            const sample = group.files[0];
            const pendingDeep = sample?.folder_pending_deep_count;
            const present = sample?.folder_present_count;
            const hasFolderStats = typeof pendingDeep === "number" && typeof present === "number";
            return (
              <Fragment key={`folder-${groupIndex}-${group.folder}`}>
                <tr className="bg-muted/20">
                  <td
                    colSpan={colSpan}
                    className="px-3 py-1.5 font-mono text-[11px] text-muted-foreground"
                  >
                    {group.folder}
                    <span className="ml-2 tabular-nums opacity-70">
                      ({group.files.length}
                      {hasFolderStats
                        ? ` on page · ${pendingDeep} pending deep / ${present} tracks`
                        : ""}
                      )
                    </span>
                  </td>
                </tr>
                {group.files.map((file) => {
                  const checked = selectable ? selectedIds!.has(file.id) : false;
                  return (
                    <tr
                      key={file.id}
                      className={cn(
                        "cursor-pointer border-b last:border-b-0 hover:bg-muted/30",
                        loading && "opacity-70",
                        checked && "bg-muted/40"
                      )}
                      onClick={() => onSelect(file)}
                    >
                      {selectable ? (
                        <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            className="h-4 w-4"
                            checked={checked}
                            onChange={(e) => toggleOne(file.id, e.target.checked)}
                            aria-label={`Select ${file.file_name}`}
                          />
                        </td>
                      ) : null}
                      <td
                        className="max-w-[28rem] truncate px-3 py-2 font-mono text-xs"
                        title={file.relative_path}
                      >
                        {file.file_name || file.relative_path}
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
                      {onSelectFolder ? (
                        <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={!file.parent_path || selectingFolderId === file.id}
                            onClick={() => onSelectFolder(file)}
                            title={file.parent_path || "No folder path"}
                          >
                            {selectingFolderId === file.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              "Select folder"
                            )}
                          </Button>
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type BulkBarProps = {
  selectedCount: number;
  busy?: boolean;
  onClear: () => void;
  onDisposition: (disposition: LibraryAuditDisposition) => void;
  onReanalyze: () => void;
  dispositions?: { label: string; value: LibraryAuditDisposition }[];
};

export function LibraryAuditBulkBar({
  selectedCount,
  busy,
  onClear,
  onDisposition,
  onReanalyze,
  dispositions = DISPOSITION_ACTIONS,
}: BulkBarProps) {
  if (selectedCount <= 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-background/70 p-3">
      <span className="text-sm font-medium tabular-nums">
        {selectedCount.toLocaleString()} selected
      </span>
      <div className="flex flex-wrap gap-2">
        {dispositions.map((action) => (
          <Button
            key={action.value}
            size="sm"
            variant={action.value === "REPLACE" ? "destructive" : "secondary"}
            disabled={busy}
            onClick={() => onDisposition(action.value)}
          >
            {action.label}
          </Button>
        ))}
        <Button size="sm" variant="outline" disabled={busy} onClick={onReanalyze}>
          {busy ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
          Queue reanalyze
        </Button>
        <Button size="sm" variant="ghost" disabled={busy} onClick={onClear}>
          Clear selection
        </Button>
      </div>
    </div>
  );
}
