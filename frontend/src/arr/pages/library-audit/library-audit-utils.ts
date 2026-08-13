import type { LibraryAuditDisposition, LibraryAuditVerdict } from "@/lib/library-audit-api";

export const PAGE_SIZE = 50;

export const DISPOSITION_ACTIONS: { label: string; value: LibraryAuditDisposition }[] = [
  { label: "Accept", value: "ACCEPTED" },
  { label: "Best Available", value: "BEST_AVAILABLE" },
  { label: "Confirmed Transcode", value: "CONFIRMED_TRANSCODE" },
  { label: "Replace", value: "REPLACE" },
  { label: "Unsure", value: "UNSURE" },
  { label: "Ignore", value: "IGNORE" },
];

export function formatDisposition(value: string | null | undefined): string {
  if (!value) return "—";
  const match = DISPOSITION_ACTIONS.find((d) => d.value === value.toUpperCase());
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
