import type { CommandEditRenderContext } from "../types";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { commandUiCopy } from "@/command-spec";

export function PlaylistSyncUrlSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editingCommand } = ctx;
  return (
    <>
      <div className="space-y-2">
        <Label>{commandUiCopy.playlistSync.playlistUrlLabel}</Label>
        <Input
          value={String(editingCommand.config_json?.playlist_url ?? "")}
          disabled
          className="font-mono text-sm"
        />
      </div>
  </>
    );
}
