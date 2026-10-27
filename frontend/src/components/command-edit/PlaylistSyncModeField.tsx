import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { commandUiCopy } from "@/command-spec";
import { playlistSyncModeFromConfig } from "./playlistSyncMode";

export function PlaylistSyncModeField({
  value,
  onChange,
}: {
  value: string | undefined;
  onChange: (mode: "full" | "append") => void;
}) {
  const ps = commandUiCopy.playlistSync;
  return (
    <div className="space-y-2">
      <Label>{ps.syncModeLabel}</Label>
      <Select
        value={playlistSyncModeFromConfig(value)}
        onValueChange={(next) => onChange(next === "append" ? "append" : "full")}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="full">{ps.syncModeFull}</SelectItem>
          <SelectItem value="append">{ps.syncModeAppend}</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}
