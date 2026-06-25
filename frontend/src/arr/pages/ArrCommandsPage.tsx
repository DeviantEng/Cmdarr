import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { CommandsPage } from "@/pages/Commands";

export function ArrCommandsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Commands"
        description="Manage, enable, and run Cmdarr commands manually or on a schedule."
      />
      <CommandsPage showPageHeader={false} showExecutions={false} useArrPanel />
    </div>
  );
}
