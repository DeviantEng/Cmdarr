import { NavLink } from "react-router-dom";
import { arrNavSections, arrPrimaryNav, type ArrNavLink } from "@/arr/arr-nav";
import { cn } from "@/lib/utils";

function SidebarLink({ item }: { item: ArrNavLink }) {
  return (
    <NavLink to={item.path} end={item.end} className="arr-sidebar-link">
      <item.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
      <span className="truncate">{item.label}</span>
    </NavLink>
  );
}

export function ArrSidebar({ className }: { className?: string }) {
  return (
    <aside
      className={cn(
        "flex h-full w-[var(--arr-sidebar-width)] shrink-0 flex-col border-r",
        className
      )}
      style={{
        background: "var(--arr-sidebar-bg)",
        borderColor: "var(--arr-sidebar-border)",
      }}
    >
      <div className="flex h-[var(--arr-header-height)] items-center gap-2 border-b px-3">
        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-sm font-bold"
          style={{
            background: "var(--arr-accent)",
            color: "var(--arr-accent-foreground)",
          }}
        >
          C
        </div>
        <div className="min-w-0">
          <div
            className="truncate text-sm font-semibold"
            style={{ color: "var(--arr-sidebar-text)" }}
          >
            Cmdarr
          </div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Modern UI</div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {arrPrimaryNav.map((item) => (
          <SidebarLink key={item.path} item={item} />
        ))}

        {arrNavSections.map((section) => (
          <div key={section.id} className="pt-2">
            <div className="arr-section-label">{section.label}</div>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <SidebarLink key={item.path} item={item} />
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
