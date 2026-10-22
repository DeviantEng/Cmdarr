import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { createCommandSubmitLabel } from "./createCommandLabels";
import { cw } from "./shared";
import type { CreateCommandWizard } from "./useCreateCommandWizard";

export function CreateCommandFooter({ wizard }: { wizard: CreateCommandWizard }) {
  const {
    embedded,
    step,
    setStep,
    playlistType,
    handleSubmit,
    canSubmit,
    isSubmitting,
    onOpenChange,
  } = wizard;
  const submitLabel = createCommandSubmitLabel(playlistType);
  const submitButton = (
    <Button onClick={handleSubmit} disabled={!canSubmit() || isSubmitting}>
      {isSubmitting ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          {cw.submitCreating}
        </>
      ) : (
        submitLabel
      )}
    </Button>
  );

  if (embedded) {
    if (step !== "form") return null;
    return (
      <div className="arr-form-footer">
        <Button variant="secondary" onClick={() => setStep("type")}>
          Back
        </Button>
        {submitButton}
      </div>
    );
  }

  return (
    <DialogFooter>
      {step === "form" ? (
        <Button variant="outline" onClick={() => setStep("type")}>
          Back
        </Button>
      ) : null}
      <Button variant="outline" onClick={() => onOpenChange(false)}>
        Cancel
      </Button>
      {step === "form" ? submitButton : null}
    </DialogFooter>
  );
}
