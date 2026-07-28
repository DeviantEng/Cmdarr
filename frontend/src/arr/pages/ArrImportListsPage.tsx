import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { ImportListsPage } from "@/pages/ImportLists";

export function ArrImportListsPage() {
  return (
    <div>
      <ArrPageHeader
        title="Import Lists"
        description="Lidarr import list endpoint for playlist sync discovery."
      />
      <ImportListsPage />
    </div>
  );
}
