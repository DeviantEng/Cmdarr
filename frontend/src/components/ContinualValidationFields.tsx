import { Label } from "@/components/ui/label";
import { NumericInput } from "@/components/NumericInput";
import { commandUiCopy } from "@/command-spec";

const cv = commandUiCopy.newReleases.continualValidation;

interface ContinualValidationFieldsProps {
  enabled: boolean;
  onEnabledChange: (enabled: boolean) => void;
  batchSize: number;
  onBatchSizeChange: (value: number) => void;
  intervalDays: number;
  onIntervalDaysChange: (value: number) => void;
  idPrefix?: string;
}

export function ContinualValidationFields({
  enabled,
  onEnabledChange,
  batchSize,
  onBatchSizeChange,
  intervalDays,
  onIntervalDaysChange,
  idPrefix = "nrd-cv",
}: ContinualValidationFieldsProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          id={`${idPrefix}-enable`}
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="rounded border-input"
        />
        <Label htmlFor={`${idPrefix}-enable`} className="cursor-pointer font-normal">
          {cv.enableLabel}
        </Label>
      </div>
      <p className="text-xs text-muted-foreground">{cv.helper}</p>
      {enabled && (
        <div className="space-y-4 rounded-lg border p-4">
          <div className="space-y-2">
            <Label htmlFor={`${idPrefix}-batch`} className="text-sm">
              {cv.batchSizeLabel}
            </Label>
            <NumericInput
              id={`${idPrefix}-batch`}
              value={batchSize}
              onChange={(v) => onBatchSizeChange(v ?? 50)}
              min={1}
              max={100}
              defaultValue={50}
            />
            <p className="text-xs text-muted-foreground">{cv.batchSizeHelp}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${idPrefix}-interval`} className="text-sm">
              {cv.intervalDaysLabel}
            </Label>
            <NumericInput
              id={`${idPrefix}-interval`}
              value={intervalDays}
              onChange={(v) => onIntervalDaysChange(v ?? 14)}
              min={1}
              max={365}
              defaultValue={14}
            />
            <p className="text-xs text-muted-foreground">{cv.intervalDaysHelp}</p>
          </div>
        </div>
      )}
    </div>
  );
}
