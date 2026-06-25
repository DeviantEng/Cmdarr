import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { StatusPage } from "@/pages/Status";

export function ArrSystemNewReleasesPage() {
  return (
    <div>
      <ArrPageHeader
        title="New Releases"
        description="Discovery scan coverage and dismissed release management."
      />
      <StatusPage sections={["new-releases"]} showPageHeader={false} useArrPanel />
    </div>
  );
}
