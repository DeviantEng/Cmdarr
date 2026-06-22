import { Navigate, useParams } from "react-router-dom";
import { ArrPageHeader } from "@/arr/components/ArrPageHeader";
import { arrSettingsSections } from "@/arr/arr-nav";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";

export function ArrSettingsPage() {
  const { section } = useParams<{ section: string }>();
  const active = arrSettingsSections.find((s) => s.slug === section);

  if (!section || !active) {
    return <Navigate to="/settings/application" replace />;
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
      <aside className="lg:w-52 lg:shrink-0">
        <nav className="arr-panel flex flex-row gap-1 overflow-x-auto p-1 lg:flex-col lg:overflow-visible">
          {arrSettingsSections.map((item) => (
            <NavLink
              key={item.slug}
              to={`/settings/${item.slug}`}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <ArrPageHeader title={active.label} description={active.description} />
        <div className="arr-panel p-6 text-sm text-muted-foreground">
          Settings fields for <strong className="text-foreground">{active.label}</strong> will be
          migrated from the classic Configuration page. Use Classic UI to edit settings until this
          section is complete.
        </div>
      </div>
    </div>
  );
}
