# Create / edit: Plex playlist destination (spec)

Commands that **create or update a playlist on Plex** (not commands that only **read** play history) use one pattern for **which Plex identity receives the playlist**.

## Scope

- **In scope:** External playlist sync (Spotify/Deezer → Plex), XMPlaylist → Plex, and any future command whose config uses `plex_account_ids` / legacy `plex_playlist_account_id` for **write** targets.
- **Out of scope:** Daylist, Local Discovery, and similar flows that pick a **play history source** (`plex_history_account_id`). Those remain a required single-account control with their own copy.

## UI rules

1. **No dropdown** for choosing “the” Plex user for playlist creation. Do not use a `Select` of accounts for this purpose.
2. **Checkbox:** `Sync to multiple Plex users` (exact label), visible only when **Target** is Plex.
3. **Unchecked:** Do not send `plex_account_ids`. Omit legacy `plex_playlist_account_id` when it means “default”. The server uses the **primary server account** (token owner).
4. **Checked:** Show the bordered checkbox group of Plex Home users from `/api/commands/plex-accounts`. User selects **one or more** accounts. A **single** non-default user is expressed as exactly one selected checkbox (same control as multi-user).
5. **Validation:** If the checkbox is checked, **at least one** account must be selected before submit/save.
6. **Helper text:** Under the checkbox, short muted copy explaining unchecked = primary account, checked = choose one or more Home users (same wording everywhere this pattern appears).

## Payload / config

- Prefer `plex_account_ids: string[]` when any specific user(s) are selected.
- Do not rely on `plex_playlist_account_id` for new saves; backend may still accept it for older configs. UIs should normalize legacy single-user configs to `sync_to_multiple_plex_users` + one id in `plex_account_ids` when loading edit forms.

## Implementation

Shared component: `frontend/src/components/PlexPlaylistTargetSection.tsx`. Use it for create (XMPlaylist, external sync) and edit (external playlist sync, XMPlaylist) so behavior and copy stay aligned.
