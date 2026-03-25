import type { CommandEditRenderContext } from "../types";
import { PlexPlaylistTargetSection } from "@/components/PlexPlaylistTargetSection";

export function PlaylistSyncPlexTargetSection({ ctx }: { ctx: CommandEditRenderContext }) {
  const { editForm, setEditForm, plexAccounts } = ctx;
  return (
    <>
      <PlexPlaylistTargetSection
        accounts={plexAccounts}
        syncToMultiple={!!editForm.sync_to_multiple_plex_users}
        selectedAccountIds={editForm.plex_account_ids ?? []}
        onSyncToMultipleChange={(checked) =>
          setEditForm((f) => ({
            ...f,
            sync_to_multiple_plex_users: checked,
            plex_account_ids: checked ? (f.plex_account_ids ?? []) : [],
          }))
        }
        onToggleAccount={(accountId, selected) =>
          setEditForm((f) => ({
            ...f,
            plex_account_ids: selected
              ? [...(f.plex_account_ids ?? []), accountId]
              : (f.plex_account_ids ?? []).filter((id) => id !== accountId),
          }))
        }
      />
  </>
    );
}
