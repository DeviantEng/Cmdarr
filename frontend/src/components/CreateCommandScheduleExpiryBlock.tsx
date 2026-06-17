import type { ReactNode } from "react";
import { commandUiCopy } from "@/command-spec/copy";
import { ExpirationFields } from "@/components/ExpirationFields";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const sch = commandUiCopy.schedule;
const cw = commandUiCopy.createWizard;

export type CreateCommandScheduleExpiryBlockProps = {
  idPrefix: string;
  scheduleOverride: boolean;
  onScheduleOverrideChange: (value: boolean) => void;
  scheduleCron: string;
  onScheduleCronChange: (value: string) => void;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  expiresAtEnabled: boolean;
  onExpiresAtEnabledChange: (value: boolean) => void;
  expiresAt: string;
  onExpiresAtChange: (value: string) => void;
  expiresAtDeletePlaylist: boolean;
  onExpiresAtDeletePlaylistChange: (value: boolean) => void;
  children?: ReactNode;
};

export function CreateCommandScheduleExpiryBlock({
  idPrefix,
  scheduleOverride,
  onScheduleOverrideChange,
  scheduleCron,
  onScheduleCronChange,
  enabled,
  onEnabledChange,
  expiresAtEnabled,
  onExpiresAtEnabledChange,
  expiresAt,
  onExpiresAtChange,
  expiresAtDeletePlaylist,
  onExpiresAtDeletePlaylistChange,
  children,
}: CreateCommandScheduleExpiryBlockProps) {
  const scheduleOverrideId = `${idPrefix}-schedule-override`;
  const enabledId = `${idPrefix}-enabled`;

  return (
    <>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id={scheduleOverrideId}
            checked={scheduleOverride}
            onChange={(e) => onScheduleOverrideChange(e.target.checked)}
            className="rounded border-input"
          />
          <Label htmlFor={scheduleOverrideId}>{sch.overrideLabel}</Label>
        </div>
        {scheduleOverride && (
          <>
            <div className="space-y-2 rounded-lg border p-4">
              <Input
                placeholder={sch.createCronPlaceholder}
                value={scheduleCron}
                onChange={(e) => onScheduleCronChange(e.target.value)}
              />
            </div>
            <p className="text-xs text-muted-foreground">{sch.createCronHelp}</p>
          </>
        )}
        {!scheduleOverride && (
          <p className="text-xs text-muted-foreground">{sch.usesGlobalDefault}</p>
        )}
      </div>
      <label className="flex items-center space-x-2">
        <input
          type="checkbox"
          id={enabledId}
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="rounded border-input"
        />
        <span className="text-sm">{cw.enableAfterCreation}</span>
      </label>
      {children}
      <ExpirationFields
        idPrefix={idPrefix}
        enabled={expiresAtEnabled}
        onEnabledChange={(v) => {
          onExpiresAtEnabledChange(v);
          if (v && !expiresAt) {
            onExpiresAtChange("");
          }
        }}
        value={expiresAt}
        onValueChange={onExpiresAtChange}
        showDeletePlaylistOption={true}
        deletePlaylistOnExpiry={expiresAtDeletePlaylist}
        onDeletePlaylistChange={onExpiresAtDeletePlaylistChange}
      />
    </>
  );
}
