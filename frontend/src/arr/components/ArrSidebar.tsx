import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { useEffect, useState } from "react";
import { arrNavSections, arrPrimaryNav, type ArrNavLink, type ArrNavSection } from "@/arr/arr-nav";
import { useAppVersion } from "@/hooks/useAppVersion";
import { cn } from "@/lib/utils";

function SidebarLink({ item, nested = false }: { item: ArrNavLink; nested?: boolean }) {
  return (
    <NavLink to={item.path} end={item.end} className={cn("arr-sidebar-link", nested && "pl-3")}>
      <item.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
      <span className="truncate">{item.label}</span>
    </NavLink>
  );
}

function CollapsibleNavSection({ section }: { section: ArrNavSection }) {
  const location = useLocation();
  const navigate = useNavigate();
  const isInSection = location.pathname.startsWith(section.pathPrefix);
  const [expanded, setExpanded] = useState(isInSection);

  useEffect(() => {
    if (isInSection) setExpanded(true);
  }, [isInSection]);

  const openSection = () => {
    setExpanded(true);
    if (isInSection) return;
    if (section.indexPath) {
      navigate(section.indexPath);
      return;
    }
    if (section.items[0]) {
      navigate(section.items[0].path);
    }
  };

  return (
    <div className={cn("arr-sidebar-section pt-1", isInSection && "is-active")}>
      <div className="flex items-center gap-0.5 pr-1">
        {section.indexPath ? (
          <NavLink
            to={section.indexPath}
            end={section.indexEnd}
            className={({ isActive }) =>
              cn(
                "arr-sidebar-link min-w-0 flex-1",
                (isActive || isInSection) && "arr-sidebar-section-title-active"
              )
            }
          >
            <section.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
            <span className="truncate">{section.label}</span>
          </NavLink>
        ) : (
          <button
            type="button"
            className={cn(
              "arr-sidebar-link min-w-0 flex-1 text-left",
              isInSection && "arr-sidebar-section-title-active"
            )}
            onClick={openSection}
          >
            <section.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
            <span className="truncate">{section.label}</span>
          </button>
        )}
        {section.items.length > 0 ? (
          <button
            type="button"
            className="arr-sidebar-chevron"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            aria-label={expanded ? `Collapse ${section.label}` : `Expand ${section.label}`}
          >
            <ChevronDown className={cn("h-4 w-4 transition-transform", expanded && "rotate-180")} />
          </button>
        ) : null}
      </div>
      {expanded && section.items.length > 0 ? (
        <div className="arr-sidebar-section-nested space-y-0.5 pt-0.5">
          {section.items.map((item) => (
            <SidebarLink key={item.path} item={item} nested />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ArrBrandMark() {
  return (
    <img
      src="/icon-512.png"
      alt=""
      width={32}
      height={32}
      className="h-8 w-8 shrink-0 rounded-md"
    />
  );
}

export function ArrSidebar({ className }: { className?: string }) {
  const version = useAppVersion();
  const commandsSection = arrNavSections.find((section) => section.id === "commands");
  const secondaryNavSections = arrNavSections.filter((section) => section.id !== "commands");

  return (
    <aside
      className={cn(
        "flex h-svh w-[var(--arr-sidebar-width)] shrink-0 flex-col overflow-hidden border-r",
        className
      )}
      style={{
        background: "var(--arr-sidebar-bg)",
        borderColor: "var(--arr-sidebar-border)",
      }}
    >
      <div
        className="flex h-[var(--arr-header-height)] items-center gap-2 border-b px-3"
        style={{ borderColor: "var(--arr-sidebar-border)" }}
      >
        <ArrBrandMark />
        <div className="min-w-0">
          <div
            className="truncate text-sm font-semibold"
            style={{ color: "var(--arr-sidebar-text)" }}
          >
            Cmdarr
          </div>
          <div className="truncate text-[10px] text-muted-foreground">Music automation</div>
        </div>
      </div>

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-y-contain p-2">
        {commandsSection ? <CollapsibleNavSection section={commandsSection} /> : null}

        {arrPrimaryNav.map((item) => (
          <SidebarLink key={item.path} item={item} />
        ))}

        {secondaryNavSections.map((section) => (
          <CollapsibleNavSection key={section.id} section={section} />
        ))}
      </nav>

      <div
        className="border-t px-3 py-2 text-[11px] text-muted-foreground"
        style={{ borderColor: "var(--arr-sidebar-border)" }}
      >
        {version ? `v${version}` : "Loading version…"}
      </div>
    </aside>
  );
}
