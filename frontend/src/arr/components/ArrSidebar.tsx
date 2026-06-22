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
    setExpanded(isInSection);
  }, [isInSection]);

  const toggleSection = () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (!isInSection && section.items[0]) {
      navigate(section.items[0].path);
    }
  };

  return (
    <div className="pt-1">
      <button
        type="button"
        className={cn(
          "arr-sidebar-link w-full text-left",
          isInSection && "text-[var(--arr-sidebar-text)]"
        )}
        onClick={toggleSection}
        aria-expanded={expanded}
      >
        <section.icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
        <span className="truncate">{section.label}</span>
        <ChevronDown
          className={cn(
            "ml-auto h-4 w-4 shrink-0 opacity-60 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>
      {expanded ? (
        <div className="ml-3 space-y-0.5 border-l border-[var(--arr-sidebar-border)] pl-1 pt-0.5">
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

  return (
    <aside
      className={cn(
        "flex h-full max-h-screen w-[var(--arr-sidebar-width)] shrink-0 flex-col border-r lg:h-screen",
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

      <nav className="flex-1 space-y-1 overflow-y-auto p-2">
        {arrPrimaryNav.map((item) => (
          <SidebarLink key={item.path} item={item} />
        ))}

        {arrNavSections.map((section) => (
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
