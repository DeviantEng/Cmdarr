import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { StatusPage } from "@/pages/Status";

export function ArrSystemLibraryCachePage() {
  return (
    <div>
      <ArrPageHeader
        title="Library Cache"
        description="Plex and Jellyfin music library cache stats and refresh controls."
      />
      <StatusPage sections={["library-cache"]} showPageHeader={false} />
    </div>
  );
}
