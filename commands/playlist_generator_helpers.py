#!/usr/bin/env python3
"""Shared helpers for playlist generator commands (Artist Essentials, Last.fm Similar, etc.)."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from utils.text_normalizer import normalize_text
from utils.track_match import artist_identity_matches

SEP = " · "
MAX_ARTIST_LEN = 40
PLAYLIST_TITLE_TOP_TRACKS_PREFIX = "[Cmdarr] Artist Essentials"
PLAYLIST_TITLE_LFM_SIMILAR_PREFIX = "[Cmdarr] Last.fm Similar"
PLAYLIST_TITLE_SETLIST_PREFIX = "[Cmdarr] Setlist"


def build_auto_playlist_suffix(artist_names: list[str]) -> str:
    """Build suffix from artist names: 1-3 artists show all, 4+ show first 2 + N More."""
    names = [n.strip()[:MAX_ARTIST_LEN] for n in artist_names if (n or "").strip()]
    if not names:
        return "Mix"
    if len(names) <= 3:
        return SEP.join(names)
    return f"{names[0]}{SEP}{names[1]} + {len(names) - 2} More"


def validate_artists_against_cache(
    artists: list[str], cached_data: dict[str, Any] | None
) -> tuple[list[str], list[str]]:
    """Validate artists against library cache. Returns (valid normalized keys, invalid display names).
    Uses exact match first, then fuzzy match (ratio >= 0.88).
    """
    if not cached_data or "artist_index" not in cached_data:
        return [], [a.strip() for a in artists if a.strip()]

    artist_index = cached_data.get("artist_index", {})
    index_keys = list(artist_index.keys())
    valid = []
    invalid = []
    fuzzy_threshold = 0.88

    for a in artists:
        name = (a or "").strip()
        if not name:
            continue
        norm = normalize_text(name.lower())
        if norm in artist_index:
            valid.append(norm)
            continue
        first_char = norm[0] if norm else ""
        candidates = [k for k in index_keys if k and k[0] == first_char]
        if not candidates and index_keys:
            candidates = index_keys
        best_ratio = 0.0
        best_key = None
        for key in candidates:
            r = SequenceMatcher(None, norm, key).ratio()
            if r > best_ratio:
                best_ratio = r
                best_key = key
        if best_key and best_ratio >= fuzzy_threshold:
            valid.append(best_key)
        else:
            invalid.append(name)
    return valid, invalid


def index_lidarr_artist_mbids_by_norm(
    name_mbid_pairs: Iterable[tuple[str, str]],
) -> dict[str, list[str]]:
    """Map normalized artist name → sorted distinct MBIDs (Lidarr / MusicBrainz)."""
    by_norm: dict[str, set[str]] = defaultdict(set)
    for name, mbid in name_mbid_pairs:
        n = normalize_text(name or "")
        mb = (mbid or "").strip()
        if n and mb:
            by_norm[n].add(mb)
    return {k: sorted(v) for k, v in by_norm.items()}


@dataclass(frozen=True)
class ResolvedArtist:
    """Library-validated artist with disambiguation metadata for playlist matching."""

    display_name: str
    norm: str
    mbids: list[str]
    library_artist: str


def load_lidarr_artist_pairs_sync() -> list[tuple[str, str]]:
    """Load ``(artist_name, artist_mbid)`` pairs from Lidarr. Returns [] if DB/query fails."""

    try:
        from database.config_models import LidarrArtist
        from database.database import get_database_manager

        db = get_database_manager()
        session = db.get_config_session_sync()
        try:
            rows = session.query(LidarrArtist).all()
            return [
                (r.artist_name or "", r.artist_mbid or "")
                for r in rows
                if (r.artist_name or "").strip() and (r.artist_mbid or "").strip()
            ]
        finally:
            session.close()
    except Exception:
        return []


def _pick_lidarr_mbids(
    display_name: str, norm: str, lidarr_pairs: list[tuple[str, str]]
) -> list[str]:
    candidates = [
        (name, mbid.strip())
        for name, mbid in lidarr_pairs
        if normalize_text(name) == norm and mbid.strip()
    ]
    if not candidates:
        return []
    if len(candidates) == 1:
        return [candidates[0][1]]
    best_name, best_mbid = max(
        candidates,
        key=lambda pair: SequenceMatcher(None, display_name.lower(), pair[0].lower()).ratio(),
    )
    return [best_mbid]


def _distinct_library_artists_for_norm(cached_data: dict[str, Any] | None, norm: str) -> list[str]:
    if not cached_data or not norm:
        return []
    artist_index = cached_data.get("artist_index", {})
    rating_keys = artist_index.get(norm, [])
    if not rating_keys:
        return []
    tracks = cached_data.get("tracks", [])
    track_by_key = {t["key"]: t for t in tracks}
    seen: set[str] = set()
    raw_artists: list[str] = []
    for key in rating_keys:
        track = track_by_key.get(key)
        if not track:
            continue
        raw = str(track.get("artist", "") or "").strip()
        if raw and raw not in seen:
            seen.add(raw)
            raw_artists.append(raw)
    return raw_artists


def _pick_library_artist(display_name: str, norm: str, cached_data: dict[str, Any] | None) -> str:
    raw_artists = _distinct_library_artists_for_norm(cached_data, norm)
    identity_matches = [r for r in raw_artists if artist_identity_matches(display_name, r)]
    pool = identity_matches or raw_artists
    if not pool:
        return display_name
    return max(
        pool,
        key=lambda r: SequenceMatcher(None, display_name.lower(), r.lower()).ratio(),
    )


def resolve_artist_track_keys(
    cached_data: dict[str, Any] | None, resolved: ResolvedArtist
) -> list[str]:
    """Rating keys for a resolved artist, filtered by identity and optional MBID index."""
    if not cached_data:
        return []
    artist_index = cached_data.get("artist_index", {})
    norm_keys = artist_index.get(resolved.norm, [])
    if not norm_keys:
        return []

    tracks = cached_data.get("tracks", [])
    track_by_key = {t["key"]: t for t in tracks}
    keys: list[str] = []
    for key in norm_keys:
        track = track_by_key.get(key)
        if not track:
            continue
        raw = str(track.get("artist", "") or "")
        if artist_identity_matches(resolved.display_name, raw):
            keys.append(key)

    mbid_index = cached_data.get("mbid_index", {})
    if resolved.mbids and mbid_index:
        mbid_keys: set[str] = set()
        for mbid in resolved.mbids:
            mbid_keys.update(mbid_index.get(mbid.lower(), []))
        if mbid_keys:
            filtered = [k for k in keys if k in mbid_keys]
            if filtered:
                keys = filtered

    return keys


def resolve_validated_artists(
    artists_raw: list[str] | str,
    cached_data: dict[str, Any] | None,
    *,
    lidarr_pairs: list[tuple[str, str]] | None = None,
) -> tuple[list[ResolvedArtist], list[str]]:
    """Validate artists and resolve display names, Lidarr MBIDs, and library raw artist strings."""
    if isinstance(artists_raw, str):
        artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
    names = [a.strip() for a in artists_raw if (a or "").strip()]
    valid_norms, invalid = validate_artists_against_cache(names, cached_data)
    valid_set = set(valid_norms)
    pairs = lidarr_pairs if lidarr_pairs is not None else load_lidarr_artist_pairs_sync()

    resolved: list[ResolvedArtist] = []
    seen_norms: set[str] = set()
    for name in names:
        norm = normalize_text(name.lower())
        if norm not in valid_set or norm in seen_norms:
            continue
        seen_norms.add(norm)
        mbids = _pick_lidarr_mbids(name, norm, pairs)
        library_artist = _pick_library_artist(name, norm, cached_data)
        resolved.append(
            ResolvedArtist(
                display_name=name,
                norm=norm,
                mbids=mbids,
                library_artist=library_artist,
            )
        )
    return resolved, invalid


def _lastfm_rows_for_resolved(
    resolved: ResolvedArtist, lastfm_tracks: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    mbid = resolved.mbids[0] if len(resolved.mbids) == 1 else None
    rows: list[dict[str, Any]] = []
    for t in lastfm_tracks[:limit]:
        track_name = (t.get("name") or "").strip()
        if not track_name:
            continue
        row: dict[str, Any] = {
            "artist": resolved.library_artist,
            "track": track_name,
            "album": t.get("album", ""),
        }
        if mbid:
            row["mbid"] = mbid
        rows.append(row)
    return rows


def _plex_popular_rows_for_resolved(
    resolved: ResolvedArtist,
    plex_client: Any,
    library_key: str,
    cached_data: dict[str, Any] | None,
    limit: int,
) -> list[dict[str, Any]]:
    track_keys = resolve_artist_track_keys(cached_data, resolved)
    if not track_keys:
        return []
    first_track_key = track_keys[0]
    artist_rk = plex_client.get_artist_rating_key_from_track(first_track_key)
    if not artist_rk:
        return []
    popular = plex_client.get_artist_popular_tracks(library_key, artist_rk, limit=limit)
    mbid = resolved.mbids[0] if len(resolved.mbids) == 1 else None
    rows: list[dict[str, Any]] = []
    for t in popular[:limit]:
        rows.append(
            {
                "rating_key": t["key"],
                "artist": t.get("artist") or resolved.library_artist,
                "track": t["title"],
                "album": t.get("album", ""),
                **({"mbid": mbid} if mbid else {}),
            }
        )
    return rows


async def fetch_top_tracks_for_artist(
    resolved: ResolvedArtist,
    *,
    lastfm_client: Any,
    plex_client: Any | None,
    library_key: str | None,
    cached_data: dict[str, Any] | None,
    limit: int,
    logger: Any,
) -> tuple[list[dict[str, Any]], str]:
    """Resolve top tracks for one artist: Last.fm (MBID/name/library name) then Plex library."""
    mbid = resolved.mbids[0] if len(resolved.mbids) == 1 else None

    lastfm_tracks = await lastfm_client.get_top_tracks(
        resolved.display_name,
        limit=limit,
        mbid=mbid,
    )
    if lastfm_tracks:
        return _lastfm_rows_for_resolved(resolved, lastfm_tracks, limit), "lastfm"

    library_name = (resolved.library_artist or "").strip()
    if library_name and library_name.lower() != resolved.display_name.lower():
        lastfm_tracks = await lastfm_client.get_top_tracks(library_name, limit=limit)
        if lastfm_tracks:
            logger.info(
                "Using Last.fm library artist name '%s' for '%s'",
                library_name,
                resolved.display_name,
            )
            return _lastfm_rows_for_resolved(resolved, lastfm_tracks, limit), "lastfm_library_name"

    if plex_client and library_key:
        plex_rows = _plex_popular_rows_for_resolved(
            resolved, plex_client, library_key, cached_data, limit
        )
        if plex_rows:
            logger.info(
                "Using Plex library tracks for '%s' (Last.fm had no data)",
                resolved.display_name,
            )
            return plex_rows, "plex"

    logger.warning(
        "No top tracks for '%s' (tried Last.fm mbid=%s, name, library name; Plex fallback empty)",
        resolved.display_name,
        mbid or "none",
    )
    return [], "none"


def load_lidarr_artist_norm_mbid_index_sync() -> dict[str, list[str]]:
    """Load ``lidarr_artist`` rows into norm → MBIDs. Returns {} if DB/query fails."""

    try:
        from database.config_models import LidarrArtist
        from database.database import get_database_manager

        db = get_database_manager()
        session = db.get_config_session_sync()
        try:
            rows = session.query(LidarrArtist).all()
            pairs = [(r.artist_name or "", r.artist_mbid or "") for r in rows]
            return index_lidarr_artist_mbids_by_norm(pairs)
        finally:
            session.close()
    except Exception:
        return {}


def merge_similar_round_robin(
    per_seed_lists: list[list[dict[str, Any]]],
    max_artists: int,
) -> list[dict[str, Any]]:
    """Interleave similar rows from each seed (round-robin) until max_artists or exhausted.
    Each row should have at least 'name' and ideally 'match' (Last.fm similarity string).
    """
    if max_artists <= 0:
        return []
    out: list[dict[str, Any]] = []
    seen_norm: set[str] = set()
    indices = [0] * len(per_seed_lists)
    while len(out) < max_artists:
        progressed = False
        for i, lst in enumerate(per_seed_lists):
            if len(out) >= max_artists:
                break
            j = indices[i]
            while j < len(lst):
                row = lst[j]
                j += 1
                name = (row.get("name") or "").strip()
                if not name:
                    continue
                norm = normalize_text(name.lower())
                if norm in seen_norm:
                    continue
                seen_norm.add(norm)
                out.append(dict(row))
                progressed = True
                indices[i] = j
                break
            else:
                indices[i] = j
        if not progressed:
            break
    return out


def build_lfm_similar_artist_pool(
    seed_names: list[str],
    per_seed_similar: list[list[dict[str, Any]]],
    include_seeds: bool,
    max_artists: int,
) -> list[dict[str, Any]]:
    """Combine optional seed rows with round-robin similar artists; dedupe by normalized name; cap size."""
    seeds_used: list[dict[str, Any]] = []
    seen: set[str] = set()
    if include_seeds:
        for sn in seed_names:
            name = (sn or "").strip()
            if not name:
                continue
            norm = normalize_text(name.lower())
            if norm in seen:
                continue
            seen.add(norm)
            seeds_used.append({"name": name, "match": "1", "mbid": "", "url": ""})
            if len(seeds_used) >= max_artists:
                return seeds_used[:max_artists]
    remaining = max(0, max_artists - len(seeds_used))
    rr = merge_similar_round_robin(per_seed_similar, remaining)
    out = list(seeds_used)
    for row in rr:
        norm = normalize_text((row.get("name") or "").lower())
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(dict(row))
        if len(out) >= max_artists:
            break
    return out[:max_artists]


def compute_lfm_similar_playlist_title(config: dict[str, Any]) -> str:
    """Full playlist title from config (matches playlist_generator_lfm_similar naming rules)."""
    seeds_raw = config.get("seed_artists")
    if seeds_raw is None:
        seeds_raw = config.get("artists", [])
    if isinstance(seeds_raw, str):
        seeds_raw = [s.strip() for s in seeds_raw.split("\n") if s.strip()]
    seeds = [s for s in seeds_raw if (s or "").strip()]
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        seed_display = [s.strip() for s in seeds if s.strip()]
        suffix = build_auto_playlist_suffix(seed_display) if seed_display else "Mix"
    return f"{PLAYLIST_TITLE_LFM_SIMILAR_PREFIX}: {suffix}"


def compute_setlistfm_playlist_title(
    config: dict[str, Any], *, artist_display_names: list[str] | None = None
) -> str:
    """Playlist title from config; uses library-validated artist names when provided."""
    if artist_display_names is not None:
        names = [a.strip() for a in artist_display_names if (a or "").strip()]
    else:
        artists_raw = config.get("artists", [])
        if isinstance(artists_raw, str):
            artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
        names = [a.strip() for a in artists_raw if (a or "").strip()]
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        suffix = build_auto_playlist_suffix(names[:50]) if names else "Mix"
    return f"{PLAYLIST_TITLE_SETLIST_PREFIX}: {suffix}"


def compute_top_tracks_playlist_title(
    artist_display_names: list[str], config: dict[str, Any]
) -> str:
    """Playlist title from validated artist display names and naming options."""
    use_custom = config.get("use_custom_playlist_name", False)
    custom = (config.get("custom_playlist_name") or "").strip()
    if use_custom and custom:
        suffix = custom
    else:
        names = [a.strip() for a in artist_display_names if (a or "").strip()]
        suffix = build_auto_playlist_suffix(names[:50]) if names else "Mix"
    return f"{PLAYLIST_TITLE_TOP_TRACKS_PREFIX}: {suffix}"


def ordered_library_validated_artist_names(
    artists_raw: list[str] | str,
    cached_data: dict[str, Any] | None,
) -> list[str]:
    """Ordered display names for title; library-validated when cache is available."""
    if isinstance(artists_raw, str):
        artists_raw = [a.strip() for a in artists_raw.split("\n") if a.strip()]
    names = [a.strip() for a in artists_raw if (a or "").strip()]
    if not cached_data or "artist_index" not in cached_data:
        return names
    valid_norms, _ = validate_artists_against_cache(names, cached_data)
    valid_set = set(valid_norms)
    return [a.strip() for a in names if normalize_text(a.lower()) in valid_set]


def get_library_cache_for_target_config(config: dict[str, Any]) -> dict[str, Any] | None:
    """Load library cache for a playlist generator target config (best-effort)."""
    try:
        from commands.config_adapter import Config
        from utils.library_cache_manager import get_library_cache_manager

        target = str(config.get("target", "plex")).lower()
        library_key = config.get("target_library_key")
        cache_manager = get_library_cache_manager(Config())
        return cache_manager.get_library_cache(target, str(library_key) if library_key else None)
    except Exception:
        return None


def compute_top_tracks_playlist_title_from_config(config: dict[str, Any]) -> str:
    """Playlist title from stored config; validates artists when library cache is available."""
    cached_data = get_library_cache_for_target_config(config)
    artists_raw = config.get("artists", [])
    names = ordered_library_validated_artist_names(artists_raw, cached_data)
    return compute_top_tracks_playlist_title(names, config)


def compute_setlistfm_playlist_title_from_config(config: dict[str, Any]) -> str:
    """Playlist title from stored config; validates artists when library cache is available."""
    cached_data = get_library_cache_for_target_config(config)
    artists_raw = config.get("artists", [])
    names = ordered_library_validated_artist_names(artists_raw, cached_data)
    return compute_setlistfm_playlist_title(config, artist_display_names=names)


def persist_playlist_identity(
    command_name: str,
    command_name_prefix: str,
    playlist_title: str,
    playlist_id: str | None,
    logger: Any,
    *,
    update_display_name: bool = True,
) -> None:
    """Persist last_playlist_title and last_playlist_id on CommandConfig after a successful sync."""
    if not command_name or not command_name.startswith(command_name_prefix):
        return
    try:
        from database.config_models import CommandConfig
        from database.database import get_database_manager

        db = get_database_manager()
        session = db.get_config_session_sync()
        try:
            cmd = (
                session.query(CommandConfig)
                .filter(CommandConfig.command_name == command_name)
                .first()
            )
            if cmd:
                cfg = dict(cmd.config_json or {})
                cfg["last_playlist_title"] = playlist_title
                if playlist_id:
                    cfg["last_playlist_id"] = str(playlist_id)
                else:
                    cfg.pop("last_playlist_id", None)
                cmd.config_json = cfg
                if update_display_name:
                    cmd.display_name = playlist_title
                session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"Could not persist playlist identity: {e}")


def delete_playlist_on_target(
    target_client: Any,
    *,
    playlist_id: str | None = None,
    playlist_title: str | None = None,
    logger: Any | None = None,
) -> None:
    """Delete a playlist by stored ID (preferred) or by name fallback."""
    log = logger
    try:
        if playlist_id:
            if hasattr(target_client, "get_playlist_by_id"):
                pl = target_client.get_playlist_by_id(playlist_id)
                if pl:
                    if pl.get("ratingKey"):
                        target_client.delete_playlist(pl["ratingKey"])
                    elif pl.get("Id"):
                        target_client.delete_playlist(pl["Id"])
                    if log:
                        log.info(f"Deleted playlist by id {playlist_id}")
                    return
            if hasattr(target_client, "delete_playlist"):
                target_client.delete_playlist(playlist_id)
                if log:
                    log.info(f"Deleted playlist by id {playlist_id}")
                return
        if playlist_title and hasattr(target_client, "find_playlist_by_name"):
            pl = target_client.find_playlist_by_name(playlist_title)
            if pl:
                if pl.get("ratingKey"):
                    target_client.delete_playlist(pl["ratingKey"])
                elif pl.get("Id"):
                    target_client.delete_playlist(pl["Id"])
                if log:
                    log.info(f"Deleted playlist '{playlist_title}' (name fallback)")
    except Exception as e:
        if log:
            log.warning(f"Could not delete playlist: {e}")
