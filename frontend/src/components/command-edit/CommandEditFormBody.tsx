import { getCommandEditSectionOrder } from "@/command-spec";
import { CommandEditSection } from "./CommandEditSection";
import type { CommandEditRenderContext } from "./types";

export function CommandEditFormBody({ ctx }: { ctx: CommandEditRenderContext }) {
  const order = getCommandEditSectionOrder(ctx.editingCommand);
  return (
    <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden px-6">
      <div className="space-y-4 py-4">
        <div className="grid gap-4">
          {order.map((sectionId) => (
            <CommandEditSection key={sectionId} sectionId={sectionId} ctx={ctx} />
          ))}
        </div>
      </div>
    </div>
  );
}
