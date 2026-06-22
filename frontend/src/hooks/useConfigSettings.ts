import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { ConfigSetting, ConnectivityTestResult } from "@/lib/types";
import { filterSettingsForCategories } from "@/lib/config-categories";
import { toast } from "sonner";

async function fetchCategoryValues(categories: string[]): Promise<Record<string, unknown>> {
  const maps = await Promise.all(categories.map((category) => api.getConfigByCategory(category)));
  const merged: Record<string, unknown> = {};
  for (const categorySettings of maps) {
    Object.assign(merged, categorySettings);
  }
  return merged;
}

async function fetchSettingDetails(configData: Record<string, unknown>): Promise<ConfigSetting[]> {
  const entries = await Promise.all(
    Object.entries(configData).map(async ([key, value]) => {
      try {
        const details = await api.getConfigDetails(key);
        return {
          ...details,
          value: value !== null && value !== undefined ? value : details.effective_value,
        } satisfies ConfigSetting;
      } catch {
        console.warn(`Failed to load details for ${key}`);
        return null;
      }
    })
  );
  return entries.filter((entry): entry is ConfigSetting => entry !== null);
}

function useConfigSettingsState(options: { loadAllOnMount?: boolean }) {
  const { loadAllOnMount = false } = options;
  const [settings, setSettings] = useState<ConfigSetting[]>([]);
  const [loading, setLoading] = useState(loadAllOnMount);
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
  const loadedKeysRef = useRef(new Set<string>());

  const mergeSettings = useCallback((incoming: ConfigSetting[]) => {
    if (incoming.length === 0) return;
    setSettings((prev) => {
      const byKey = new Map(prev.map((setting) => [setting.key, setting]));
      for (const setting of incoming) {
        byKey.set(setting.key, setting);
      }
      return Array.from(byKey.values());
    });
  }, []);

  const loadAllConfiguration = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const configData = await api.getAllConfig();
      const detailedSettings = await fetchSettingDetails(configData);
      loadedKeysRef.current = new Set(detailedSettings.map((setting) => setting.key));
      setSettings(detailedSettings);
    } catch (err) {
      setError("Failed to load configuration");
      toast.error("Failed to load configuration");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCategories = useCallback(
    async (categories: string[]) => {
      if (categories.length === 0) {
        setLoading(false);
        return;
      }

      setError(null);
      try {
        const configData = await fetchCategoryValues(categories);
        const pendingData = Object.fromEntries(
          Object.entries(configData).filter(([key]) => !loadedKeysRef.current.has(key))
        );

        if (Object.keys(pendingData).length === 0) {
          setLoading(false);
          return;
        }

        setLoading(true);
        const detailedSettings = await fetchSettingDetails(pendingData);
        for (const setting of detailedSettings) {
          loadedKeysRef.current.add(setting.key);
        }
        mergeSettings(detailedSettings);
      } catch (err) {
        setError("Failed to load configuration");
        toast.error("Failed to load configuration");
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [mergeSettings]
  );

  useEffect(() => {
    if (loadAllOnMount) {
      void loadAllConfiguration();
    }
  }, [loadAllConfiguration, loadAllOnMount]);

  const handleSettingChange = useCallback(
    (key: string, value: unknown) => {
      setSettings((prev) =>
        prev.map((setting) => (setting.key === key ? { ...setting, value } : setting))
      );
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
        setSettings((prev) =>
          prev.map((setting) => (setting.key === key ? { ...setting, value: "***" } : setting))
        );
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
          const setting = settings.find((entry) => entry.key === key);
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
      await loadAllConfiguration();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save configuration");
    }
  }, [changedSettings, loadAllConfiguration, settings]);

  const handleReset = useCallback(() => {
    void loadAllConfiguration();
    setChangedSettings(new Set());
    toast.info("Changes reset");
  }, [loadAllConfiguration]);

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
    loadConfiguration: loadAllConfiguration,
    loadCategories,
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

export type ConfigSettingsController = ReturnType<typeof useConfigSettingsState>;

const ConfigSettingsContext = createContext<ConfigSettingsController | null>(null);

export function ConfigSettingsProvider({ children }: { children: ReactNode }) {
  const controller = useConfigSettingsState({ loadAllOnMount: false });
  return createElement(ConfigSettingsContext.Provider, { value: controller }, children);
}

export function useConfigSettings() {
  return useConfigSettingsState({ loadAllOnMount: true });
}

export function useArrConfigSettings(categories: string[]) {
  const context = useContext(ConfigSettingsContext);
  if (!context) {
    throw new Error("useArrConfigSettings must be used within ConfigSettingsProvider");
  }

  const categoriesKey = categories.join("\0");

  useEffect(() => {
    if (!categoriesKey) return;
    void context.loadCategories(categoriesKey.split("\0"));
  }, [context, categoriesKey]);

  return context;
}
