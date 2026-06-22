import { Navigate, useParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import {
  ConfigApiKeyCard,
  ConfigConnectivityDialog,
  ConfigSettingsErrorBanner,
  ConfigSettingsList,
  ConfigSettingsToolbar,
} from "@/components/config/ConfigSettingsFields";
import { getConfigCategoryGroup } from "@/lib/config-categories";
import { useConfigSettings } from "@/hooks/useConfigSettings";

export function ArrSettingsPage() {
  const { section } = useParams<{ section: string }>();
  const group = section ? getConfigCategoryGroup(section) : undefined;
  const controller = useConfigSettings();

  if (!section || !group) {
    return <Navigate to="/settings/application" replace />;
  }

  if (controller.loading) {
    return (
      <div className="flex min-h-[240px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const groupSettings = controller.getSettingsByCategories(group.categories);

  return (
    <div>
      <ArrPageHeader
        title={group.name}
        description={`Configure ${group.name.toLowerCase()} settings.`}
      />
      {section === "application" ? <ConfigApiKeyCard controller={controller} /> : null}
      <ConfigSettingsErrorBanner controller={controller} />
      <div className="mb-4">
        <ConfigSettingsToolbar controller={controller} />
      </div>
      <ConfigSettingsList controller={controller} groupSettings={groupSettings} useArrPanel />
      <ConfigConnectivityDialog controller={controller} />
    </div>
  );
}
