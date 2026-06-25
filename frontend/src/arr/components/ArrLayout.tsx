import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ArrHeader } from "@/arr/components/ArrHeader";
import { ArrSidebar } from "@/arr/components/ArrSidebar";
import { ConfigSettingsProvider } from "@/hooks/useConfigSettings";
import { cn } from "@/lib/utils";

export function ArrLayout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const prevHtml = document.documentElement.style.overflow;
    const prevBody = document.body.style.overflow;
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    return () => {
      document.documentElement.style.overflow = prevHtml;
      document.body.style.overflow = prevBody;
    };
  }, []);

  return (
    <ConfigSettingsProvider>
      <div
        data-ui-shell="arr"
        className="arr-shell flex h-svh max-h-svh overflow-hidden flex-col lg:flex-row"
        style={{ background: "var(--arr-content-bg)" }}
      >
        <div className="hidden shrink-0 lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:flex">
          <ArrSidebar />
        </div>

        {mobileNavOpen ? (
          <div className="fixed inset-0 z-50 lg:hidden" role="presentation">
            <button
              type="button"
              className="absolute inset-0 bg-black/50"
              aria-label="Close navigation"
              onClick={() => setMobileNavOpen(false)}
            />
            <div className="absolute inset-y-0 left-0 shadow-xl">
              <ArrSidebar />
            </div>
          </div>
        ) : null}

        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden lg:pl-[var(--arr-sidebar-width)]">
          <ArrHeader onOpenSidebar={() => setMobileNavOpen(true)} />
          <main
            className={cn(
              "min-h-0 flex-1 overflow-x-hidden overflow-y-auto overscroll-y-contain p-4 sm:p-6"
            )}
          >
            {children}
          </main>
        </div>
      </div>
    </ConfigSettingsProvider>
  );
}
