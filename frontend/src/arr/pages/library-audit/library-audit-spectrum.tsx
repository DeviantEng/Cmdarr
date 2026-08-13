import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { libraryAuditApi, type LibraryAuditSpectrumCurve } from "@/lib/library-audit-api";
import { extractSpectrumCurve } from "./library-audit-utils";

type SpectrumSvgProps = {
  curve: LibraryAuditSpectrumCurve;
  className?: string;
};

export function SpectrumCurveSvg({ curve, className }: SpectrumSvgProps) {
  const width = 640;
  const height = 180;
  const padL = 36;
  const padR = 12;
  const padT = 12;
  const padB = 28;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const nyquist = curve.nyquist_hz > 0 ? curve.nyquist_hz : Math.max(...curve.freqs_hz, 1);

  const points = curve.freqs_hz
    .map((freq, i) => {
      const x = padL + (freq / nyquist) * plotW;
      const y = padT + (1 - Math.min(1, Math.max(0, curve.norm[i] ?? 0))) * plotH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const cutoff = curve.cutoff_hz;
  const cutoffX =
    cutoff != null && cutoff > 0 ? padL + (Math.min(cutoff, nyquist) / nyquist) * plotW : null;

  const ticks = [0.25, 0.5, 0.75, 1].map((f) => ({
    x: padL + f * plotW,
    label: `${Math.round((f * nyquist) / 1000)}k`,
  }));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      role="img"
      aria-label="Magnitude spectrum"
    >
      <rect
        x={padL}
        y={padT}
        width={plotW}
        height={plotH}
        className="fill-background stroke-border"
      />
      {ticks.map((t) => (
        <g key={t.label}>
          <line
            x1={t.x}
            y1={padT}
            x2={t.x}
            y2={padT + plotH}
            className="stroke-border"
            strokeWidth={1}
          />
          <text
            x={t.x}
            y={height - 8}
            textAnchor="middle"
            className="fill-muted-foreground"
            style={{ fontSize: 10 }}
          >
            {t.label}
          </text>
        </g>
      ))}
      <polyline
        fill="none"
        points={points}
        stroke="oklch(58% 0.14 195)"
        strokeWidth={1.5}
      />
      {cutoffX != null ? (
        <>
          <line
            x1={cutoffX}
            y1={padT}
            x2={cutoffX}
            y2={padT + plotH}
            className="stroke-destructive"
            strokeWidth={1.25}
            strokeDasharray="4 3"
          />
          <text
            x={Math.min(cutoffX + 4, width - padR - 40)}
            y={padT + 12}
            className="fill-destructive"
            style={{ fontSize: 10 }}
          >
            {(cutoff! / 1000).toFixed(1)} kHz
          </text>
        </>
      ) : null}
      <text x={6} y={padT + 10} className="fill-muted-foreground" style={{ fontSize: 10 }}>
        dB
      </text>
    </svg>
  );
}

type SpectrumPanelProps = {
  fileId: number | null;
  open: boolean;
  extension: string | null | undefined;
  isPresent: boolean;
  evidence: unknown;
};

export function LibraryAuditSpectrumPanel({
  fileId,
  open,
  extension,
  isPresent,
  evidence,
}: SpectrumPanelProps) {
  const embedded = extractSpectrumCurve(evidence);
  const [curve, setCurve] = useState<LibraryAuditSpectrumCurve | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || fileId == null) {
      setCurve(null);
      setError(null);
      setLoading(false);
      return;
    }

    const fromEvidence = extractSpectrumCurve(evidence);
    if (fromEvidence) {
      setCurve(fromEvidence);
      setError(null);
      setLoading(false);
      return;
    }

    if (!isPresent) {
      setCurve(null);
      return;
    }
    const ext = (extension || "").toLowerCase();
    if (ext !== ".flac" && ext !== "flac") {
      setCurve(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    void libraryAuditApi
      .getSpectrum(fileId)
      .then((res) => {
        if (!cancelled) setCurve(res.spectrum_curve);
      })
      .catch((e) => {
        if (!cancelled) {
          setCurve(null);
          setError(e instanceof Error ? e.message : "Spectrum unavailable");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, fileId, evidence, extension, isPresent]);

  if (!isPresent) return null;
  const ext = (extension || "").toLowerCase();
  if (ext !== ".flac" && ext !== "flac" && !embedded) return null;

  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted-foreground">Spectrum</div>
      {loading ? (
        <div className="flex min-h-[120px] items-center justify-center rounded-md border border-border">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      ) : curve ? (
        <div className="rounded-md border border-border bg-background/50 p-2">
          <SpectrumCurveSvg curve={curve} className="h-auto w-full" />
          <p className="mt-1 text-[11px] text-muted-foreground">
            Peak-normalised magnitude spectrum
            {curve.cutoff_hz != null
              ? ` · detected cutoff ${(curve.cutoff_hz / 1000).toFixed(1)} kHz`
              : ""}
            {embedded ? " · from analysis" : " · computed on demand (not stored)"}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{error || "Spectrum unavailable."}</p>
      )}
    </div>
  );
}
