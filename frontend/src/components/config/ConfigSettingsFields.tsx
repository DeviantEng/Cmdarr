import { Save, RotateCcw, Check, AlertCircle, Search, Eye, EyeOff } from "lucide-react";
import type { ConfigSetting } from "@/lib/types";
import type { ConfigSettingsController } from "@/hooks/useConfigSettings";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NumericInput } from "@/components/NumericInput";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export function ConfigSettingsToolbar({ controller }: { controller: ConfigSettingsController }) {
  const {
    searchQuery,
    setSearchQuery,
    handleTestConnectivity,
    testingConnectivity,
    handleReset,
    handleSaveAll,
    changedSettings,
  } = controller;

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="relative w-full sm:max-w-xs">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search settings..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-9 pl-8"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleTestConnectivity()}
          disabled={testingConnectivity}
        >
          <Check className="mr-2 h-4 w-4" />
          Test Connectivity
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={handleReset}
          disabled={changedSettings.size === 0}
        >
          <RotateCcw className="mr-2 h-4 w-4" />
          Reset
        </Button>
        <Button
          size="sm"
          onClick={() => void handleSaveAll()}
          disabled={changedSettings.size === 0}
        >
          <Save className="mr-2 h-4 w-4" />
          Save Changes
          {changedSettings.size > 0 ? (
            <Badge variant="secondary" className="ml-2">
              {changedSettings.size}
            </Badge>
          ) : null}
        </Button>
      </div>
    </div>
  );
}

export function ConfigApiKeyCard({
  controller,
  variant = "legacy",
}: {
  controller: ConfigSettingsController;
  variant?: "legacy" | "arr";
}) {
  const { apiKeyGenerated, generatingApiKey, handleGenerateApiKey } = controller;
  const isArr = variant === "arr";

  return (
    <Card className={cn(isArr ? "arr-panel arr-settings-api-key" : "p-4")}>
      <div className="space-y-2">
        <Label className="text-sm font-medium">API Key</Label>
        <p className="text-sm text-muted-foreground">
          Use this key for external API calls. Pass via{" "}
          <code className="rounded bg-muted px-1">X-API-Key</code> or{" "}
          <code className="rounded bg-muted px-1">Authorization: Bearer &lt;key&gt;</code>.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-2">
          <Button
            variant="outline"
            size="sm"
            className="shrink-0 self-start"
            onClick={() => void handleGenerateApiKey()}
            disabled={generatingApiKey}
          >
            {generatingApiKey ? "Generating..." : "Generate API Key"}
          </Button>
          {apiKeyGenerated ? (
            <div className="min-w-0 break-all rounded bg-muted p-2 font-mono text-sm">
              {apiKeyGenerated}
            </div>
          ) : null}
        </div>
        {apiKeyGenerated ? (
          <p className="text-xs text-destructive">
            Store this key now. It will not be shown again.
          </p>
        ) : null}
      </div>
    </Card>
  );
}

export function ConfigSettingsErrorBanner({
  controller,
}: {
  controller: ConfigSettingsController;
}) {
  const { error, loadConfiguration } = controller;
  if (!error) return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-destructive/50 bg-destructive/10 p-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="min-w-0 text-sm text-destructive">{error}</p>
      <Button
        variant="outline"
        size="sm"
        className="shrink-0 self-start sm:self-auto"
        onClick={() => void loadConfiguration()}
      >
        Try Again
      </Button>
    </div>
  );
}

export function ConfigConnectivityDialog({ controller }: { controller: ConfigSettingsController }) {
  const {
    showConnectivityDialog,
    setShowConnectivityDialog,
    testingConnectivity,
    connectivityResults,
  } = controller;

  return (
    <Dialog open={showConnectivityDialog} onOpenChange={setShowConnectivityDialog}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connectivity Test Results</DialogTitle>
          <DialogDescription>
            {testingConnectivity ? "Testing connections..." : "Test complete"}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {connectivityResults.map((result, idx) => (
            <div
              key={idx}
              className={cn(
                "rounded-lg border p-3",
                result.status === "success" &&
                  "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950",
                result.status === "warning" &&
                  "border-yellow-200 bg-yellow-50 dark:border-yellow-900 dark:bg-yellow-950",
                result.status === "error" &&
                  "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950"
              )}
            >
              <div className="flex items-start gap-2">
                <div className="mt-0.5">
                  {result.status === "success" ? (
                    <Check className="h-5 w-5 text-green-600" />
                  ) : (
                    <AlertCircle
                      className={cn(
                        "h-5 w-5",
                        result.status === "error" ? "text-red-600" : "text-yellow-600"
                      )}
                    />
                  )}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{result.service}</div>
                  <div className="text-sm text-muted-foreground">{result.message}</div>
                  {result.error ? (
                    <div className="mt-1 text-xs text-destructive">{result.error}</div>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

type ConfigSettingsListProps = {
  controller: ConfigSettingsController;
  groupSettings: ConfigSetting[];
  useArrPanel?: boolean;
};

export function ConfigSettingsList({
  controller,
  groupSettings,
  useArrPanel = false,
}: ConfigSettingsListProps) {
  const { handleSettingChange, handleRevealToggle, getSensitiveDisplayValue, revealedKeys } =
    controller;

  const renderSettingInput = (setting: ConfigSetting) => {
    switch (setting.data_type) {
      case "bool":
        return (
          <Switch
            checked={setting.value === true || setting.value === "true"}
            onCheckedChange={(checked) => handleSettingChange(setting.key, checked)}
          />
        );
      case "int":
      case "float":
        return (
          <NumericInput
            value={
              setting.value !== null && setting.value !== undefined && setting.value !== ""
                ? Number(setting.value)
                : Number(setting.default_value) || 0
            }
            onChange={(v) => handleSettingChange(setting.key, v)}
            numericType={setting.data_type === "float" ? "float" : "int"}
            defaultValue={Number(setting.default_value) || 0}
            placeholder={setting.default_value}
            className={cn(setting.is_sensitive && "font-mono")}
          />
        );
      case "dropdown":
        return (
          <Select
            value={String(setting.value || setting.default_value)}
            onValueChange={(v) => handleSettingChange(setting.key, v)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(setting.options || []).map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "json":
        return (
          <Textarea
            value={String(setting.value ?? "")}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            placeholder={setting.default_value}
            rows={3}
            className="font-mono text-xs"
          />
        );
      default:
        if (setting.is_sensitive) {
          const isRevealed = revealedKeys.has(setting.key);
          return (
            <div className="flex min-w-0 w-full gap-2">
              <Input
                type={isRevealed ? "text" : "password"}
                value={getSensitiveDisplayValue(setting)}
                onChange={(e) => handleSettingChange(setting.key, e.target.value)}
                placeholder={setting.default_value}
                className="min-w-0 flex-1 font-mono"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => void handleRevealToggle(setting.key)}
                title={isRevealed ? "Hide" : "Show key"}
              >
                {isRevealed ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </Button>
            </div>
          );
        }
        return (
          <Input
            type="text"
            value={String(setting.value ?? "")}
            onChange={(e) => handleSettingChange(setting.key, e.target.value)}
            placeholder={setting.default_value}
          />
        );
    }
  };

  if (groupSettings.length === 0) {
    return (
      <div
        className={cn(
          "p-8 text-center text-sm text-muted-foreground",
          useArrPanel && "arr-panel",
          !useArrPanel && "rounded-lg border"
        )}
      >
        No settings found in this category
      </div>
    );
  }

  if (useArrPanel) {
    return (
      <fieldset className="arr-settings-fieldset">
        {groupSettings.map((setting) => (
          <div key={setting.key} className="arr-settings-row">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Label htmlFor={setting.key} className="arr-settings-label">
                  {setting.key}
                </Label>
                {setting.is_required ? (
                  <Badge variant="destructive" className="text-xs">
                    Required
                  </Badge>
                ) : null}
                {setting.is_sensitive ? (
                  <Badge variant="secondary" className="text-xs">
                    Sensitive
                  </Badge>
                ) : null}
              </div>
              <p className="arr-settings-help">
                {setting.description || "No description available"}
              </p>
            </div>
            <div className="arr-settings-control">{renderSettingInput(setting)}</div>
          </div>
        ))}
      </fieldset>
    );
  }

  return (
    <div className="grid gap-3">
      {groupSettings.map((setting) => (
        <Card key={setting.key} className={cn("p-4", useArrPanel && "arr-panel")}>
          <div className="grid min-w-0 gap-3 lg:grid-cols-[1fr,min(300px,100%)] lg:gap-4">
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Label htmlFor={setting.key} className="text-sm font-medium">
                  {setting.key}
                </Label>
                {setting.is_required ? (
                  <Badge variant="destructive" className="text-xs">
                    Required
                  </Badge>
                ) : null}
                {setting.is_sensitive ? (
                  <Badge variant="secondary" className="text-xs">
                    Sensitive
                  </Badge>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">
                {setting.description || "No description available"}
              </p>
            </div>
            <div className="flex min-w-0 items-start">{renderSettingInput(setting)}</div>
          </div>
        </Card>
      ))}
    </div>
  );
}
