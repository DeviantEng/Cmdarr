import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { EventsPage } from "@/pages/Events";

export function ArrEventsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Artist Events"
        description="Upcoming shows and festivals for artists in your Lidarr library."
      />
      <EventsPage showPageHeader={false} useArrPanel />
    </div>
  );
}
