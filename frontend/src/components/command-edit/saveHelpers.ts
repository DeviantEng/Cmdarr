import { toExpiresAtIso } from "@/lib/expiration";
import type { CommandEditFormState } from "./types";

export function buildSchedulePayload(editForm: CommandEditFormState) {
  return {
    schedule_override: editForm.schedule_override,
    schedule_cron: editForm.schedule_override ? editForm.schedule_cron : undefined,
  };
}

export function applyExpiryToConfig(
  cfg: Record<string, unknown>,
  editForm: CommandEditFormState
): void {
  if (editForm.expires_at_enabled && editForm.expires_at) {
    cfg.expires_at = toExpiresAtIso(editForm.expires_at);
    cfg.expires_at_delete_playlist = editForm.expires_at_delete_playlist ?? true;
  } else {
    delete cfg.expires_at;
    delete cfg.expires_at_delete_playlist;
  }
}

export function buildScheduleAndExpiryConfig(
  editForm: CommandEditFormState,
  configJson: Record<string, unknown>
): {
  schedule_override?: boolean;
  schedule_cron?: string;
  config_json: Record<string, unknown>;
} {
  const cfg = { ...configJson };
  applyExpiryToConfig(cfg, editForm);
  return { ...buildSchedulePayload(editForm), config_json: cfg };
}
