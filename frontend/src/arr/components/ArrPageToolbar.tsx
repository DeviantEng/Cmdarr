import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type ArrPageToolbarProps = {
  children: ReactNode;
  className?: string;
};

/** Toolbar row inside an arr-panel (matches Settings page pattern). */
export function ArrPageToolbar({ children, className }: ArrPageToolbarProps) {
  return (
    <div className={cn("arr-panel arr-page-toolbar-panel overflow-hidden", className)}>
      <div className="arr-page-toolbar px-4 py-3">{children}</div>
    </div>
  );
}

type ArrContentPanelProps = {
  children: ReactNode;
  className?: string;
};

/** Primary content panel for Arr pages (tables, lists, forms). */
export function ArrContentPanel({ children, className }: ArrContentPanelProps) {
  return (
    <div className={cn("arr-panel arr-content-panel overflow-hidden", className)}>{children}</div>
  );
}

type ArrSectionHeaderProps = {
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function ArrSectionHeader({ title, description, actions }: ArrSectionHeaderProps) {
  return (
    <div className="arr-section-header flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold">{title}</h2>
        {description ? (
          <p className="mt-1 text-xs leading-snug text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

export function ArrPanelBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("arr-panel-body p-4", className)}>{children}</div>;
}
