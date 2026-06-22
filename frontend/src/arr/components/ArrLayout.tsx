import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { ArrHeader } from "@/arr/components/ArrHeader";
import { ArrSidebar } from "@/arr/components/ArrSidebar";
import { cn } from "@/lib/utils";

export function ArrLayout({ children }: { children: ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileNavOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileNavOpen]);

  return (
    <div
      data-ui-shell="arr"
      className="arr-shell flex min-h-screen flex-col lg:flex-row"
      style={{ background: "var(--arr-content-bg)" }}
    >
      <div className="hidden lg:flex">
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

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <ArrHeader onOpenSidebar={() => setMobileNavOpen(true)} />
        <main className={cn("min-w-0 flex-1 overflow-x-hidden p-4 sm:p-6")}>{children}</main>
      </div>
    </div>
  );
}
