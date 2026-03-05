import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

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

interface ExpirationFieldsProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  value: string;
  onValueChange: (value: string) => void;
  idPrefix?: string;
}

export function ExpirationFields({
  enabled,
  onEnabledChange,
  value,
  onValueChange,
  idPrefix = "exp",
}: ExpirationFieldsProps) {
  const minDatetime = (() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    const h = String(now.getHours()).padStart(2, "0");
    const min = String(now.getMinutes()).padStart(2, "0");
    return `${y}-${m}-${d}T${h}:${min}`;
  })();

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={`${idPrefix}-enable`}
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="rounded border-input"
        />
        <Label htmlFor={`${idPrefix}-enable`} className="cursor-pointer font-normal">
          Enable expiration
        </Label>
      </div>
      {enabled && (
        <div className="space-y-2 pl-6">
          <Label htmlFor={`${idPrefix}-datetime`} className="text-sm">
            Expires at
          </Label>
          <Input
            id={`${idPrefix}-datetime`}
            type="datetime-local"
            min={minDatetime}
            value={value}
            onChange={(e) => onValueChange(e.target.value)}
            className="max-w-xs"
          />
          <p className="text-xs text-muted-foreground">
            When this time passes, the command will be disabled (not deleted) and its playlist
            removed from the target.
          </p>
        </div>
      )}
    </div>
  );
}
