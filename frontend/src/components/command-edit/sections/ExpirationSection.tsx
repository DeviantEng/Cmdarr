import type { CommandEditRenderContext } from "../types";
import { ExpirationFields } from "@/components/ExpirationFields";

export function ExpirationSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm } = ctx;
  return (
    <>
      <ExpirationFields
        idPrefix="edit-exp"
        enabled={editForm.expires_at_enabled ?? false}
        onEnabledChange={(v) =>
          setEditForm((f) => ({
            ...f,
            expires_at_enabled: v,
            expires_at: v && !f.expires_at ? "" : f.expires_at,
          }))
        }
        value={editForm.expires_at ?? ""}
        onValueChange={(v) => setEditForm((f) => ({ ...f, expires_at: v }))}
        showDeletePlaylistOption={true}
        deletePlaylistOnExpiry={editForm.expires_at_delete_playlist ?? true}
        onDeletePlaylistChange={(v) =>
          setEditForm((f) => ({ ...f, expires_at_delete_playlist: v }))
        }
      />
    </>
  );
}
