import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { CommandExecutionsPanel } from "@/components/CommandExecutionsPanel";

export function ArrCommandHistoryPage() {
  return (
    <div>
      <ArrPageHeader
        title="History"
        description="Recent command runs with status, timing, and details."
      />
      <div className="arr-page-panels">
        <CommandExecutionsPanel useArrPanel />
      </div>
    </div>
  );
}
