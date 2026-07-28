import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { DiscoveryLastfmPage } from "@/pages/DiscoveryLastfm";

export function ArrDiscoveryLastfmPage() {
  return (
    <div>
      <ArrPageHeader
        title="Last.fm Discovery"
        description="Browse similar artists and add them to Lidarr. Scheduled auto-add lives under Commands (independent of this page)."
      />
      <DiscoveryLastfmPage showPageHeader={false} useArrPanel />
    </div>
  );
}
