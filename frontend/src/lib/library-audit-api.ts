import { api } from "@/lib/api";

export type LibraryAuditDisposition =
  | "FALSE_POSITIVE"
  | "BEST_AVAILABLE"
  | "CONFIRMED_TRANSCODE"
  | "REPLACE"
  | "UNSURE"
  | "IGNORE";

export type LibraryAuditVerdict =
  | "AUTHENTIC"
  | "WARNING"
  | "SUSPICIOUS"
  | "FAKE_CERTAIN"
  | "INCONCLUSIVE"
  | "ERROR"
  | string;

export type LibraryAuditAnalysisState =
  | "PENDING"
  | "ANALYZING"
  | "ANALYZED"
  | "ERROR"
  | "STALE"
  | "UNSUPPORTED"
  | string;

export type LibraryAuditSpectrumCurve = {
  freqs_hz: number[];
  norm: number[];
  nyquist_hz: number;
  cutoff_hz?: number | null;
  segment_seconds?: number;
};

export type LibraryAuditSpectrumResponse = {
  file_id: number;
  spectrum_curve: LibraryAuditSpectrumCurve;
  cutoff_hz?: number | null;
};

export type LibraryAuditAnalysis = {
  id: number;
  file_id: number;
  provider: string | null;
  provider_version: string | null;
  provider_mode: string | null;
  /** Display verdict (False Positive disposition overrides scan to AUTHENTIC). */
  verdict: LibraryAuditVerdict;
  /** Original analyzer verdict before disposition override. */
  scan_verdict?: LibraryAuditVerdict | null;
  verdict_overridden?: boolean;
  score: number | null;
  confidence: number | null;
  cutoff_hz: number | null;
  is_hires_suspect: boolean | null;
  summary: string | null;
  evidence: unknown;
  raw_result: unknown;
  content_hash: string | null;
  file_size_bytes: number | null;
  file_mtime_ns: number | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
};

export type LibraryAuditReview = {
  id: number;
  file_id: number;
  analysis_id: number | null;
  content_hash: string | null;
  disposition: LibraryAuditDisposition | string;
  note: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
};

export type LibraryAuditFile = {
  id: number;
  relative_path: string;
  file_name: string;
  parent_path: string | null;
  extension: string | null;
  size_bytes: number | null;
  mtime_ns: number | null;
  content_hash: string | null;
  is_present: boolean;
  missing_since: string | null;
  analysis_state: LibraryAuditAnalysisState;
  analysis_queued_at: string | null;
  analysis_attempts: number;
  last_analysis_error: string | null;
  current_analysis_id: number | null;
  current_review_id: number | null;
  artist: string | null;
  album: string | null;
  title: string | null;
  track_number: number | null;
  disc_number: number | null;
  sample_rate: number | null;
  bits_per_sample: number | null;
  channels: number | null;
  duration_seconds: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  analysis: LibraryAuditAnalysis | null;
  review: LibraryAuditReview | null;
};

export type LibraryAuditProviderStatus = {
  name: string | null;
  version: string | null;
  healthy: boolean;
  message: string | null;
  modes?: string[];
  extensions?: string[];
};

export type LibraryAuditStatus = {
  enabled: boolean;
  root: string;
  root_ok: boolean;
  root_message: string;
  provider: LibraryAuditProviderStatus;
};

export type LibraryAuditInventoryRun = {
  id: number;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  root_path: string | null;
  files_seen: number | null;
  eligible_files_seen: number | null;
  new_files: number | null;
  changed_files: number | null;
  missing_files: number | null;
  errors: number | null;
  duration_seconds: number | null;
  error_message: string | null;
};

export type LibraryAuditAnalysisRun = {
  id: number;
  started_at: string | null;
  completed_at: string | null;
  status: string;
  requested_limit?: number | null;
  attempted?: number | null;
  completed?: number | null;
  provider?: string | null;
  provider_version?: string | null;
  duration_seconds?: number | null;
  error_message?: string | null;
};

export type LibraryAuditStats = LibraryAuditStatus & {
  library: {
    present: number;
    missing: number;
    analyzed: number;
    pending: number;
    unsupported?: number;
    errors: number;
  };
  formats?: {
    by_kind: {
      lossless: number;
      lossy: number;
      unknown: number;
    };
    by_extension: Record<string, number>;
  };
  verdicts: {
    authentic: number;
    warning: number;
    suspicious: number;
    fake_certain: number;
    inconclusive: number;
    error: number;
  };
  review: {
    needs_review: number;
    false_positive: number;
    best_available: number;
    confirmed_transcode: number;
    replace: number;
    ignored: number;
    unsure: number;
  };
  last_inventory_run: LibraryAuditInventoryRun | null;
  last_analysis_run: LibraryAuditAnalysisRun | null;
};

export type LibraryAuditFilesResponse = {
  total: number;
  limit: number;
  offset: number;
  items: LibraryAuditFile[];
};

export type LibraryAuditListResponse<T> = {
  items: T[];
};

export type LibraryAuditTestCheck = {
  name: string;
  success: boolean;
  message: string;
  root?: string;
  provider?: string;
  version?: string | null;
};

export type LibraryAuditTestResult = {
  success: boolean;
  checks: LibraryAuditTestCheck[];
};

export type LibraryAuditFilesQuery = {
  limit?: number;
  offset?: number;
  present?: boolean | null;
  analysis_state?: string | null;
  verdict?: string | null;
  disposition?: string | null;
  needs_review?: boolean | null;
  q?: string | null;
};

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const libraryAuditApi = {
  getStatus() {
    return api.request<LibraryAuditStatus>("/api/library-audit/status");
  },

  getStats() {
    return api.request<LibraryAuditStats>("/api/library-audit/stats");
  },

  listFiles(query: LibraryAuditFilesQuery = {}) {
    const qs = buildQuery({
      limit: query.limit,
      offset: query.offset,
      present: query.present ?? undefined,
      analysis_state: query.analysis_state ?? undefined,
      verdict: query.verdict ?? undefined,
      disposition: query.disposition ?? undefined,
      needs_review: query.needs_review ?? undefined,
      q: query.q ?? undefined,
    });
    return api.request<LibraryAuditFilesResponse>(`/api/library-audit/files${qs}`);
  },

  getFile(id: number) {
    return api.request<LibraryAuditFile>(`/api/library-audit/files/${id}`);
  },

  listAnalyses(id: number) {
    return api.request<LibraryAuditListResponse<LibraryAuditAnalysis>>(
      `/api/library-audit/files/${id}/analyses`
    );
  },

  listReviews(id: number) {
    return api.request<LibraryAuditListResponse<LibraryAuditReview>>(
      `/api/library-audit/files/${id}/reviews`
    );
  },

  submitReview(id: number, body: { disposition: LibraryAuditDisposition; note?: string }) {
    return api.request<LibraryAuditReview>(`/api/library-audit/files/${id}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  clearReview(id: number) {
    return api.request<LibraryAuditFile>(`/api/library-audit/files/${id}/review/clear`, {
      method: "POST",
    });
  },

  reanalyze(id: number) {
    return api.request<LibraryAuditFile>(`/api/library-audit/files/${id}/reanalyze`, {
      method: "POST",
    });
  },

  getSpectrum(id: number) {
    return api.request<LibraryAuditSpectrumResponse>(`/api/library-audit/files/${id}/spectrum`);
  },

  test() {
    return api.request<LibraryAuditTestResult>("/api/library-audit/test", { method: "POST" });
  },
};
