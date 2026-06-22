import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { StatusPage } from "@/pages/Status";

export function ArrSystemArtistEventsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Artist Events"
        description="Cached event scan coverage and cache management."
      />
      <StatusPage sections={["artist-events"]} showPageHeader={false} />
    </div>
  );
}
