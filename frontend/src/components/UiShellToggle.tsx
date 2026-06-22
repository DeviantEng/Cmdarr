import { LayoutTemplate, PanelTop } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUiShell } from "@/lib/ui-shell";
import { cn } from "@/lib/utils";

type UiShellToggleProps = {
  className?: string;
  compact?: boolean;
};

export function UiShellToggle({ className, compact = false }: UiShellToggleProps) {
  const { isArr, toggleShell } = useUiShell();

  return (
    <Button
      variant={isArr ? "secondary" : "ghost"}
      size={compact ? "sm" : "default"}
      className={cn(compact ? "h-9 gap-1.5 px-2.5" : "h-10 gap-2", className)}
      onClick={toggleShell}
      title={
        isArr ? "Switch to classic UI" : "Preview modern *arr UI (work in progress)"
      }
    >
      {isArr ? (
        <>
          <PanelTop className="h-4 w-4 shrink-0" />
          {!compact ? <span className="hidden sm:inline">Classic UI</span> : null}
        </>
      ) : (
        <>
          <LayoutTemplate className="h-4 w-4 shrink-0" />
          {!compact ? <span className="hidden sm:inline">Modern UI</span> : null}
        </>
      )}
    </Button>
  );
}
