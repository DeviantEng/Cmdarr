import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ConfigApiKeyCard,
  ConfigConnectivityDialog,
  ConfigSettingsErrorBanner,
  ConfigSettingsList,
  ConfigSettingsToolbar,
} from "@/components/config/ConfigSettingsFields";
import { useConfigSettings } from "@/hooks/useConfigSettings";
import { legacyConfigCategoryGroups } from "@/lib/config-categories";

export function ConfigPage() {
  const controller = useConfigSettings();
  const [activeTab, setActiveTab] = useState("application");

  if (controller.loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Configuration</h1>
          <p className="mt-2 text-muted-foreground">Manage your Cmdarr configuration settings</p>
        </div>
        <div className="flex justify-center py-12 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" />
          Loading configuration...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Configuration</h1>
        <p className="mt-2 text-muted-foreground">Manage your Cmdarr configuration settings</p>
      </div>

      <ConfigApiKeyCard controller={controller} />
      <ConfigSettingsErrorBanner controller={controller} />
      <ConfigSettingsToolbar controller={controller} />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid h-auto w-full grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-7">
          {legacyConfigCategoryGroups.map((group) => (
            <TabsTrigger key={group.tabValue} value={group.tabValue} className="text-xs sm:text-sm">
              <span className="mr-1 hidden sm:inline">{group.icon}</span>
              <span className="truncate">{group.name}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        {legacyConfigCategoryGroups.map((group) => (
          <TabsContent key={group.tabValue} value={group.tabValue} className="space-y-4">
            <ConfigSettingsList
              controller={controller}
              groupSettings={controller.getSettingsByCategories(group.categories)}
            />
          </TabsContent>
        ))}
      </Tabs>

      <ConfigConnectivityDialog controller={controller} />
    </div>
  );
}
