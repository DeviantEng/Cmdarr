import { Link } from "react-router";
import { Radio } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ArrContentPanel, ArrPanelBody, ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { Button } from "@/components/ui/button";

export function ArrDiscoveryPage() {
  return (
    <div className="arr-page-panels space-y-6">
      <ArrPageHeader
        title="Discovery"
        description="Interactive and scheduled tools for finding artists to add to Lidarr."
      />
      <ArrContentPanel>
        <ArrSectionHeader title="Last.fm" />
        <ArrPanelBody className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Browse similar artists from your Lidarr library or Plex top listens, review bios, and
            add to Lidarr. The scheduled Last.fm Discovery command (Commands) can auto-add on a
            cadence using the same Lidarr API path — interactive and scheduled stay independent.
          </p>
          <Button asChild size="sm">
            <Link to="/discovery/lastfm">
              <Radio className="h-4 w-4" />
              Open Last.fm Discovery
            </Link>
          </Button>
        </ArrPanelBody>
      </ArrContentPanel>
    </div>
  );
}
