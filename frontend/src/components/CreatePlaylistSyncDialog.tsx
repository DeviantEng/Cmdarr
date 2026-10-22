import { ArrContentPanel } from "@/arr/components/ArrPageToolbar";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { CreateCommandFormBody } from "./create-command/CreateCommandFormBody";
import { useCreateCommandWizard } from "./create-command/useCreateCommandWizard";
import type { CreatePlaylistSyncDialogProps } from "./create-command/shared";

export type { CreatePlaylistSyncDialogProps };

export function CreatePlaylistSyncDialog(props: CreatePlaylistSyncDialogProps) {
  const wizard = useCreateCommandWizard(props);
  if (!props.embedded && !props.open) return null;
  const formBody = <CreateCommandFormBody wizard={wizard} />;
  if (props.embedded) {
    return <ArrContentPanel>{formBody}</ArrContentPanel>;
  }
  return (
    <Dialog open={props.open} onOpenChange={props.onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">{formBody}</DialogContent>
    </Dialog>
  );
}
