/** Convert datetime-local value (YYYY-MM-DDTHH:mm) to ISO string for API */
export function toExpiresAtIso(value: string): string {
  if (!value || !value.trim()) return "";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "";
  return d.toISOString();
}

/** Convert ISO string from API to datetime-local value for input */
export function fromExpiresAtIso(iso: string | null | undefined): string {
  if (!iso || !iso.trim()) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day}T${h}:${min}`;
}
