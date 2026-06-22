import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ImportListsPage } from "@/pages/ImportLists";

export function ArrImportListsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Import Lists"
        description="Lidarr import list endpoints for Last.fm and playlist sync discovery."
      />
      <ImportListsPage showPageHeader={false} useArrPanel />
    </div>
  );
}
