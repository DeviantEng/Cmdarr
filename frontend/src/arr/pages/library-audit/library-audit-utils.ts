import type {
  LibraryAuditDisposition,
  LibraryAuditSpectrumCurve,
  LibraryAuditVerdict,
} from "@/lib/library-audit-api";

export const PAGE_SIZE = 50;

export function extractSpectrumCurve(evidence: unknown): LibraryAuditSpectrumCurve | null {
  if (!evidence || typeof evidence !== "object") return null;
  const curve = (evidence as { spectrum_curve?: unknown }).spectrum_curve;
  if (!curve || typeof curve !== "object") return null;
  const c = curve as LibraryAuditSpectrumCurve;
  if (!Array.isArray(c.freqs_hz) || !Array.isArray(c.norm)) return null;
  if (c.freqs_hz.length < 2 || c.freqs_hz.length !== c.norm.length) return null;
  return c;
}

export const DISPOSITION_ACTIONS: { label: string; value: LibraryAuditDisposition }[] = [
  { label: "False Positive", value: "FALSE_POSITIVE" },
  { label: "Best Available", value: "BEST_AVAILABLE" },
  { label: "Confirmed Transcode", value: "CONFIRMED_TRANSCODE" },
  { label: "Replace", value: "REPLACE" },
  { label: "Unsure", value: "UNSURE" },
  { label: "Ignore", value: "IGNORE" },
];

export function formatDisposition(value: string | null | undefined): string {
  if (!value) return "—";
  const normalized = value.toUpperCase() === "ACCEPTED" ? "FALSE_POSITIVE" : value.toUpperCase();
  const match = DISPOSITION_ACTIONS.find((d) => d.value === normalized);
  if (match) return match.label;
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatVerdict(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function verdictBadgeVariant(
  verdict: LibraryAuditVerdict | null | undefined
): "default" | "secondary" | "destructive" | "outline" {
  const v = (verdict || "").toUpperCase();
  if (v === "AUTHENTIC") return "default";
  if (v === "WARNING" || v === "INCONCLUSIVE") return "secondary";
  if (v === "SUSPICIOUS" || v === "FAKE_CERTAIN" || v === "ERROR") return "destructive";
  return "outline";
}
