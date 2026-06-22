import { useEffect, useState } from "react";
import { api } from "@/lib/api";

let cachedVersion: string | null = null;
let versionPromise: Promise<string | null> | null = null;

async function fetchAppVersion(): Promise<string | null> {
  if (cachedVersion) return cachedVersion;
  if (!versionPromise) {
    versionPromise = api
      .getVersion()
      .then((response) => {
        cachedVersion = response.version;
        return cachedVersion;
      })
      .catch(() => null)
      .finally(() => {
        versionPromise = null;
      });
  }
  return versionPromise;
}

export function useAppVersion() {
  const [version, setVersion] = useState<string | null>(cachedVersion);

  useEffect(() => {
    if (cachedVersion) {
      setVersion(cachedVersion);
      return;
    }
    void fetchAppVersion().then(setVersion);
  }, []);

  return version;
}
