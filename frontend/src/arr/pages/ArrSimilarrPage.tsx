import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { SimilarrPage } from "@/pages/Similarr";

export function ArrSimilarrPage() {
  return (
    <div>
      <ArrPageHeader
        title="Similarr"
        description="Discover similar artists via Last.fm from your Lidarr library and add them with album search."
      />
      <SimilarrPage showPageHeader={false} useArrPanel />
    </div>
  );
}
