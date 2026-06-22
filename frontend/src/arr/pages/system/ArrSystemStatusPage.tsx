import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { useAppVersion } from "@/hooks/useAppVersion";
import { StatusPage } from "@/pages/Status";

const STATUS_SECTIONS = ["health", "system-info", "migrations", "api-endpoints"] as const;

export function ArrSystemStatusPage() {
  const version = useAppVersion();

  return (
    <div>
      <ArrPageHeader
        title="Status"
        description={
          version
            ? `Application health, uptime, execution stats, and database migrations · v${version}`
            : "Application health, uptime, execution stats, and database migrations."
        }
      />
      <StatusPage sections={[...STATUS_SECTIONS]} showPageHeader={false} useArrPanel />
    </div>
  );
}
