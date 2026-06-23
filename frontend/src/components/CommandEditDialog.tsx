import type { ReactNode } from "react";
import { commandUiCopy } from "@/command-spec/copy";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { CommandConfig } from "@/lib/types";

type CommandEditDialogProps = {
  command: CommandConfig | null;
  onOpenChange: (open: boolean) => void;
  formBody: ReactNode;
  footer: ReactNode;
};

export function CommandEditDialog({
  command,
  onOpenChange,
  formBody,
  footer,
}: CommandEditDialogProps) {
  return (
    <Dialog open={!!command} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 pt-6 pb-4 flex-shrink-0">
          <DialogTitle className="flex flex-wrap items-center gap-2">
            <span>Edit Command: {command?.display_name}</span>
            {command && (
              <Badge variant={command.enabled ? "default" : "secondary"}>
                {command.enabled ? "Enabled" : "Disabled"}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>{commandUiCopy.base.dialogDescription}</DialogDescription>
        </DialogHeader>
        {command && (
          <>
            {formBody}
            <div className="flex-shrink-0 flex justify-end gap-2 border-t border-[var(--dialog-border)] px-6 py-4">
              {footer}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
