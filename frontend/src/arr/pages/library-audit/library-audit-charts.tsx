import { cn } from "@/lib/utils";

export type PieSlice = {
  label: string;
  value: number;
  color?: string;
};

const DEFAULT_COLORS = [
  "oklch(58% 0.14 195)",
  "oklch(62% 0.12 145)",
  "oklch(72% 0.13 85)",
  "oklch(64% 0.15 45)",
  "oklch(58% 0.17 25)",
  "oklch(52% 0.08 280)",
  "oklch(48% 0.03 260)",
  "oklch(66% 0.1 220)",
];

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function slicePath(
  cx: number,
  cy: number,
  rOuter: number,
  rInner: number,
  startAngle: number,
  endAngle: number
): string {
  const large = endAngle - startAngle > 180 ? 1 : 0;
  const o1 = polar(cx, cy, rOuter, startAngle);
  const o2 = polar(cx, cy, rOuter, endAngle);
  const i2 = polar(cx, cy, rInner, endAngle);
  const i1 = polar(cx, cy, rInner, startAngle);
  if (rInner <= 0) {
    return [
      `M ${cx} ${cy}`,
      `L ${o1.x} ${o1.y}`,
      `A ${rOuter} ${rOuter} 0 ${large} 1 ${o2.x} ${o2.y}`,
      "Z",
    ].join(" ");
  }
  return [
    `M ${o1.x} ${o1.y}`,
    `A ${rOuter} ${rOuter} 0 ${large} 1 ${o2.x} ${o2.y}`,
    `L ${i2.x} ${i2.y}`,
    `A ${rInner} ${rInner} 0 ${large} 0 ${i1.x} ${i1.y}`,
    "Z",
  ].join(" ");
}

type StatPieChartProps = {
  slices: PieSlice[];
  size?: number;
  className?: string;
  emptyLabel?: string;
  /** Max slices before collapsing the rest into Other */
  maxSlices?: number;
};

export function StatPieChart({
  slices,
  size = 168,
  className,
  emptyLabel = "No data yet.",
  maxSlices,
}: StatPieChartProps) {
  let working = slices
    .map((s) => ({ ...s, value: Math.max(0, Number(s.value) || 0) }))
    .filter((s) => s.value > 0)
    .sort((a, b) => b.value - a.value);

  if (maxSlices != null && working.length > maxSlices) {
    const head = working.slice(0, maxSlices - 1);
    const rest = working.slice(maxSlices - 1);
    const otherValue = rest.reduce((sum, s) => sum + s.value, 0);
    working = [...head, { label: "Other", value: otherValue }];
  }

  const total = working.reduce((sum, s) => sum + s.value, 0);
  if (total <= 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }

  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size * 0.42;
  const rInner = size * 0.24;
  const arcs = working.reduce<
    { label: string; value: number; color: string; path: string; pct: number; endAngle: number }[]
  >((acc, slice, i) => {
    const start = acc.length ? acc[acc.length - 1].endAngle : 0;
    const sweep = (slice.value / total) * 360;
    const end = start + sweep;
    const path =
      working.length === 1
        ? slicePath(cx, cy, rOuter, rInner, 0, 359.99)
        : slicePath(cx, cy, rOuter, rInner, start, end);
    acc.push({
      label: slice.label,
      value: slice.value,
      color: slice.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length],
      path,
      pct: (slice.value / total) * 100,
      endAngle: end,
    });
    return acc;
  }, []);

  return (
    <div className={cn("flex flex-col items-center gap-3 sm:flex-row sm:items-start", className)}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="shrink-0"
        role="img"
        aria-label="Distribution chart"
      >
        {arcs.map((arc) => (
          <path key={arc.label} d={arc.path} fill={arc.color} stroke="transparent" />
        ))}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-foreground"
          style={{ fontSize: 14, fontWeight: 600 }}
        >
          {total.toLocaleString()}
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          className="fill-muted-foreground"
          style={{ fontSize: 10 }}
        >
          total
        </text>
      </svg>
      <ul className="w-full min-w-0 space-y-1.5 text-sm">
        {arcs.map((arc) => (
          <li key={arc.label} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: arc.color }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-muted-foreground">{arc.label}</span>
            <span className="tabular-nums text-foreground">{arc.value.toLocaleString()}</span>
            <span className="w-12 text-right tabular-nums text-xs text-muted-foreground">
              {arc.pct < 1 && arc.pct > 0 ? "<1%" : `${Math.round(arc.pct)}%`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
