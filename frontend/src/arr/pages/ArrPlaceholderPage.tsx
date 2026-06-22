import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { SlidersHorizontal } from "lucide-react";

type ArrPlaceholderPageProps = {
  title: string;
  description: string;
};

export function ArrPlaceholderPage({ title, description }: ArrPlaceholderPageProps) {
  return (
    <div>
      <ArrPageHeader title={title} description={description} />
      <div className="arr-panel flex min-h-[280px] flex-col items-center justify-center gap-3 p-8 text-center">
        <SlidersHorizontal className="h-10 w-10 text-muted-foreground opacity-60" />
        <div>
          <p className="font-medium">Modern UI preview</p>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            This page is part of the new *arr-style interface for v0.3.17. Functionality will be
            migrated here from the classic UI. Toggle back to Classic UI to use full features today.
          </p>
        </div>
      </div>
    </div>
  );
}
