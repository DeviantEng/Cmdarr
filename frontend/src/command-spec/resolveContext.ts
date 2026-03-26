import type { CommandConfig } from "@/lib/types";
import type { ResolveContext } from "./uiTypes";

/** Build resolver context from the edit dialog’s active command. */
export function resolveContextForEditCommand(cmd: CommandConfig): ResolveContext {
  const cfg = cmd.config_json || {};
  return {
    mode: "edit",
    commandName: cmd.command_name,
    configJson: cfg,
    target: typeof cfg.target === "string" ? cfg.target : undefined,
    source: typeof cfg.source === "string" ? cfg.source : undefined,
  };
}

/** Build resolver context from create wizard state. */
export function resolveContextForCreate(params: {
  playlistType: string;
  target?: string;
  source?: string;
}): ResolveContext {
  return {
    mode: "create",
    playlistType: params.playlistType,
    target: params.target,
    source: params.source,
  };
}
