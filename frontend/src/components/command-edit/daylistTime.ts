/** Daylist time-period defaults and helpers (command edit + save). */
export const DEFAULT_DAYLIST_TIME_PERIODS: Record<string, { start: number; end: number }> = {
  Dawn: { start: 3, end: 5 },
  "Early Morning": { start: 6, end: 8 },
  Morning: { start: 9, end: 11 },
  Afternoon: { start: 12, end: 15 },
  Evening: { start: 16, end: 18 },
  Night: { start: 19, end: 21 },
  "Late Night": { start: 22, end: 2 },
};

export function hoursFromRange(start: number, end: number): number[] {
  if (end >= start) return Array.from({ length: end - start + 1 }, (_, i) => start + i);
  return [
    ...Array.from({ length: 24 - start }, (_, i) => start + i),
    ...Array.from({ length: end + 1 }, (_, i) => i),
  ];
}

export function hoursToRange(hours: number[]): { start: number; end: number } {
  if (hours.length === 0) return { start: 0, end: 0 };
  const low = hours.filter((h) => h < 12);
  const high = hours.filter((h) => h >= 12);
  if (low.length > 0 && high.length > 0) return { start: Math.min(...high), end: Math.max(...low) };
  return { start: Math.min(...hours), end: Math.max(...hours) };
}
