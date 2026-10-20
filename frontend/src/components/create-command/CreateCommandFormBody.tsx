import { ArrSectionHeader } from "@/arr/components/ArrPageToolbar";
import { DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { createCommandDescription, createCommandTitle } from "./createCommandLabels";
import { CreateCommandFooter } from "./CreateCommandFooter";
import { CreateCommandFormFields } from "./CreateCommandFormFields";
import { CreateCommandTypeStep } from "./CreateCommandTypeStep";
import type { CreateCommandWizard } from "./useCreateCommandWizard";

export function CreateCommandFormBody({ wizard }: { wizard: CreateCommandWizard }) {
  const { embedded, step, playlistType } = wizard;
  const createTitle = createCommandTitle(step, playlistType);
  const createDescription = createCommandDescription(step, playlistType);

  return (
    <>
      {!embedded ? (
        <DialogHeader>
          <DialogTitle>{createTitle}</DialogTitle>
          <DialogDescription>{createDescription}</DialogDescription>
        </DialogHeader>
      ) : step === "form" ? (
        <ArrSectionHeader title={createTitle} description={createDescription} />
      ) : null}
      {step === "type" ? (
        <CreateCommandTypeStep wizard={wizard} />
      ) : (
        <CreateCommandFormFields wizard={wizard} />
      )}
      <CreateCommandFooter wizard={wizard} />
    </>
  );
}
