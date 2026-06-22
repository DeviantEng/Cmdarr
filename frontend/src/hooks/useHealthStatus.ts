import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type HealthState = {
  status: "healthy" | "unhealthy" | "unknown";
  message: string;
};

export function useHealthStatus(pollMs = 60_000) {
  const [health, setHealth] = useState<HealthState>({ status: "unknown", message: "Checking…" });

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const result = await api.healthCheck();
        if (cancelled) return;
        setHealth({
          status: result.status === "healthy" ? "healthy" : "unhealthy",
          message: result.message,
        });
      } catch {
        if (cancelled) return;
        setHealth({ status: "unhealthy", message: "Unable to reach health endpoint" });
      }
    };

    void check();
    const interval = setInterval(() => void check(), pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollMs]);

  return health;
}
