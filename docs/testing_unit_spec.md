# Unit testing spec (Cmdarr)

This document defines conventions for **Phase 6a**; feature-specific tests should follow it.

## Clients (`clients/`)

- **Scope:** HTTP wrappers, response normalization, validation (e.g. enum query params).
- **Do not** call real remote APIs in unit tests; mock `_make_request` or the HTTP layer.
- **Fixtures:** Store sample JSON under `tests/fixtures/` when responses are large; inline small dicts otherwise.
- **Assert:** Public return shapes (e.g. list of `{track, artist, album}`), error handling, and optional static headers (e.g. `User-Agent`) when policy requires it.

## Commands (`commands/`)

- **Scope:** Orchestration, `last_run_stats`, config validation branches.
- **Mock:** External clients (`PlexClient`, `JellyfinClient`, `XmplaylistClient`, etc.) and `sync_playlist` results.
- **Assert:** Success/failure, keys in `last_run_stats` used by `CommandExecutor._generate_output_summary`, and that `sync_playlist` receives the expected track list shape.

## Optional later (separate initiative)

- **`utils/`:** Pure functions — table-driven tests, edge cases.
- **`services/`:** Prefer unit tests only for deterministic branches; integration tests for full flows.
- **`app/api/`:** FastAPI `TestClient` for routes (auth/env setup as needed).

## Tooling

- `pytest` + `pytest-asyncio` for async tests.
- File naming: `tests/test_<module_name>.py`.
