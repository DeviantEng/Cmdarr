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
