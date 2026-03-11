import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SetupPage } from "@/pages/Setup";
import { LoginPage } from "@/pages/Login";

type AuthState = "loading" | "setup" | "login" | "authenticated";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>("loading");

  useEffect(() => {
    let cancelled = false;
    api
      .getAuthStatus()
      .then((res) => {
        if (cancelled) return;
        if (res.setup_required) {
          setState("setup");
        } else if (res.authenticated) {
          setState("authenticated");
        } else {
          setState("login");
        }
      })
      .catch(() => {
        if (cancelled) return;
        setState("login");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (state === "setup") {
    return <SetupPage />;
  }

  if (state === "login") {
    return <LoginPage />;
  }

  return <>{children}</>;
}
