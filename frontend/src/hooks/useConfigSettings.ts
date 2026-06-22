import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { ConfigSetting, ConnectivityTestResult } from "@/lib/types";
import { filterSettingsForCategories } from "@/lib/config-categories";
import { toast } from "sonner";

export function useConfigSettings() {
  const [settings, setSettings] = useState<ConfigSetting[]>([]);
  const [loading, setLoading] = useState(true);
  const [changedSettings, setChangedSettings] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [testingConnectivity, setTestingConnectivity] = useState(false);
  const [connectivityResults, setConnectivityResults] = useState<ConnectivityTestResult[]>([]);
  const [showConnectivityDialog, setShowConnectivityDialog] = useState(false);
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [revealedValues, setRevealedValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [apiKeyGenerated, setApiKeyGenerated] = useState<string | null>(null);
  const [generatingApiKey, setGeneratingApiKey] = useState(false);

  const loadConfiguration = useCallback(async () => {
    setError(null);
    try {
      const configData = await api.getAllConfig();
      const detailedSettings: ConfigSetting[] = [];
      for (const [key, value] of Object.entries(configData)) {
        try {
          const details = await api.getConfigDetails(key);
          detailedSettings.push({
            ...details,
            value: value !== null && value !== undefined ? value : details.effective_value,
          });
        } catch {
          console.warn(`Failed to load details for ${key}`);
        }
      }
      setSettings(detailedSettings);
    } catch (err) {
      setError("Failed to load configuration");
      toast.error("Failed to load configuration");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfiguration();
  }, [loadConfiguration]);

  const handleSettingChange = useCallback(
    (key: string, value: unknown) => {
      setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value } : s)));
      setChangedSettings((prev) => new Set(prev).add(key));
      if (revealedKeys.has(key)) {
        setRevealedValues((prev) => ({ ...prev, [key]: String(value ?? "") }));
      }
    },
    [revealedKeys]
  );

  const handleRevealToggle = useCallback(
    async (key: string) => {
      if (revealedKeys.has(key)) {
        setRevealedKeys((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
        setRevealedValues((prev) => {
          const rest = { ...prev };
          delete rest[key];
          return rest;
        });
        setSettings((prev) => prev.map((s) => (s.key === key ? { ...s, value: "***" } : s)));
        setChangedSettings((prev) => {
          const next = new Set(prev);
          next.delete(key);
          return next;
        });
      } else {
        try {
          const details = await api.getConfigDetails(key, { reveal: true });
          const value = details.effective_value ?? "";
          setRevealedKeys((prev) => new Set(prev).add(key));
          setRevealedValues((prev) => ({ ...prev, [key]: String(value) }));
          handleSettingChange(key, value);
        } catch {
          toast.error("Failed to load value");
        }
      }
    },
    [handleSettingChange, revealedKeys]
  );

  const getSensitiveDisplayValue = useCallback(
    (setting: ConfigSetting) => {
      if (revealedKeys.has(setting.key)) {
        return revealedValues[setting.key] ?? setting.value ?? "";
      }
      return "***";
    },
    [revealedKeys, revealedValues]
  );

  const handleSaveAll = useCallback(async () => {
    try {
      await Promise.all(
        Array.from(changedSettings).map(async (key) => {
          const setting = settings.find((s) => s.key === key);
          if (!setting) return;
          try {
            await api.updateConfigSetting(key, {
              value: setting.value,
              data_type: setting.data_type,
            });
          } catch {
            throw new Error(`Failed to save ${key}`);
          }
        })
      );
      toast.success("Configuration saved successfully");
      setChangedSettings(new Set());
      await loadConfiguration();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save configuration");
    }
  }, [changedSettings, loadConfiguration, settings]);

  const handleReset = useCallback(() => {
    void loadConfiguration();
    setChangedSettings(new Set());
    toast.info("Changes reset");
  }, [loadConfiguration]);

  const handleTestConnectivity = useCallback(async () => {
    setTestingConnectivity(true);
    setShowConnectivityDialog(true);
    try {
      const results = await api.testConnectivity();
      setConnectivityResults(results.results);
      if (results.overall_success) {
        toast.success("All connectivity tests passed!");
      } else {
        toast.warning("Some connectivity tests failed");
      }
    } catch (err) {
      toast.error("Connectivity test failed");
      console.error(err);
    } finally {
      setTestingConnectivity(false);
    }
  }, []);

  const handleGenerateApiKey = useCallback(async () => {
    setGeneratingApiKey(true);
    setApiKeyGenerated(null);
    try {
      const res = await api.generateApiKey();
      setApiKeyGenerated(res.api_key);
      toast.success("API key generated. Store it securely.");
    } catch {
      toast.error("Failed to generate API key");
    } finally {
      setGeneratingApiKey(false);
    }
  }, []);

  const filteredSettings = useMemo(() => {
    if (!searchQuery) return settings;
    const q = searchQuery.toLowerCase();
    return settings.filter(
      (setting) =>
        setting.key.toLowerCase().includes(q) || setting.description.toLowerCase().includes(q)
    );
  }, [searchQuery, settings]);

  const getSettingsByCategories = useCallback(
    (categories: string[]) => filterSettingsForCategories(filteredSettings, categories),
    [filteredSettings]
  );

  return {
    settings,
    loading,
    changedSettings,
    searchQuery,
    setSearchQuery,
    testingConnectivity,
    connectivityResults,
    showConnectivityDialog,
    setShowConnectivityDialog,
    revealedKeys,
    error,
    apiKeyGenerated,
    generatingApiKey,
    loadConfiguration,
    handleSettingChange,
    handleRevealToggle,
    getSensitiveDisplayValue,
    handleSaveAll,
    handleReset,
    handleTestConnectivity,
    handleGenerateApiKey,
    getSettingsByCategories,
  };
}

export type ConfigSettingsController = ReturnType<typeof useConfigSettings>;
