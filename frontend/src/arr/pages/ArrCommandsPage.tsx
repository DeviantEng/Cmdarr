import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { CommandsPage } from "@/pages/Commands";

export function ArrCommandsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Commands"
        description="Manage and monitor scheduled and manual Cmdarr commands."
      />
      <CommandsPage showPageHeader={false} useArrPanel />
    </div>
  );
}
