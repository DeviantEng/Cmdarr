import { commandUiCopy } from "@/command-spec";

const plexT = commandUiCopy.plexPlaylistTarget;

export type PlexPlaylistTargetAccount = { id: string; name: string };

type PlexPlaylistTargetSectionProps = {
  accounts: PlexPlaylistTargetAccount[];
  syncToMultiple: boolean;
  selectedAccountIds: string[];
  onSyncToMultipleChange: (checked: boolean) => void;
  onToggleAccount: (accountId: string, selected: boolean) => void;
};

/**
 * Plex playlist destination: checkbox + account list per
 * docs/create_command_plex_playlist_target_spec.md (no per-user Select).
 */
export function PlexPlaylistTargetSection({
  accounts,
  syncToMultiple,
  selectedAccountIds,
  onSyncToMultipleChange,
  onToggleAccount,
}: PlexPlaylistTargetSectionProps) {
  return (
    <div className="space-y-2">
      <label className="flex cursor-pointer items-center gap-2">
        <input
          type="checkbox"
          checked={syncToMultiple}
          onChange={(e) => onSyncToMultipleChange(e.target.checked)}
          className="rounded border-input"
        />
        <span className="text-sm font-medium">{plexT.syncToMultipleLabel}</span>
      </label>
      <p className="text-xs text-muted-foreground pl-6">{plexT.helper}</p>
      {syncToMultiple && (
        <div className="flex flex-wrap gap-3 rounded-lg border p-3">
          {accounts.map((acc) => (
            <label key={acc.id} className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={selectedAccountIds.includes(acc.id)}
                onChange={(e) => onToggleAccount(acc.id, e.target.checked)}
                className="rounded border-input"
              />
              {acc.name || `Account ${acc.id}`}
            </label>
          ))}
          {accounts.length === 0 && (
            <span className="text-sm text-muted-foreground">{plexT.noAccounts}</span>
          )}
        </div>
      )}
    </div>
  );
}
