import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { CommandExecutionsPanel } from "@/components/CommandExecutionsPanel";

export function ArrCommandHistoryPage() {
  return (
    <div>
      <ArrPageHeader
        title="History"
        description="Recent command runs, status, and execution details."
      />
      <div className="arr-page-panels">
        <CommandExecutionsPanel useArrPanel />
      </div>
    </div>
  );
}
