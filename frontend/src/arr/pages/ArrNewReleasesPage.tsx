import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { NewReleasesPage } from "@/pages/NewReleases";

export function ArrNewReleasesPage() {
  return (
    <div>
      <ArrPageHeader
        title="New Releases"
        description="Find releases from your Lidarr artists that are missing from MusicBrainz."
      />
      <NewReleasesPage showPageHeader={false} useArrPanel />
    </div>
  );
}
