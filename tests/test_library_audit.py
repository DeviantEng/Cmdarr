#!/usr/bin/env python3
"""Tests for Library Audit path safety, inventory, and review semantics."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from database.database import DatabaseManager
from database.library_audit_models import LibraryAuditFile
from services.library_audit.hashing import sha256_file
from services.library_audit.inventory import run_inventory
from services.library_audit.paths import UnsafePathError, resolve_under_root
from services.library_audit.provider import (
    ProviderAnalysisResult,
    ProviderCapabilities,
    ProviderHealth,
)
from services.library_audit.retention import cleanup_missing_records
from services.library_audit.service import (
    analyze_file,
    create_review,
    queue_reanalyze,
    recover_stale_analyzing,
    run_analysis_batch,
)


class FakeProvider:
    def __init__(self, verdict: str = "SUSPICIOUS", score: float = 60.0):
        self.verdict = verdict
        self.score = score
        self.calls: list[str] = []

    def health(self) -> ProviderHealth:
        return ProviderHealth(healthy=True, provider="fake", provider_version="0.0.1")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider="fake", extensions=[".flac"])

    def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
        self.calls.append(absolute_path)
        return ProviderAnalysisResult(
            provider="fake",
            provider_version="0.0.1",
            provider_mode=mode,
            verdict=self.verdict,
            score=self.score,
            confidence="test",
            summary="fake result",
            cutoff_hz=16000.0,
            evidence={"fake": True},
            raw_result={"verdict": self.verdict, "score": self.score},
            metadata={"title": Path(absolute_path).stem, "artist": "Test Artist"},
        )


@pytest.fixture()
def audit_env(tmp_path: Path):
    """Isolated config/cache/audit DBs + music root with two FLAC fixtures."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    music = tmp_path / "music"
    music.mkdir()
    album = music / "Artist" / "Album"
    album.mkdir(parents=True)

    def write_flac(path: Path, freq: float = 440.0):
        sr = 44100
        t = np.linspace(0, 0.25, int(sr * 0.25), endpoint=False)
        tone = (0.2 * np.sin(2 * np.pi * freq * t)).astype(np.float64)
        stereo = np.column_stack([tone, tone])
        sf.write(str(path), stereo, sr, format="FLAC", subtype="PCM_16")

    f1 = album / "01 - Track.flac"
    f2 = album / "02 - Track.flac"
    write_flac(f1, 440.0)
    write_flac(f2, 880.0)
    (music / "readme.txt").write_text("ignore me")

    # Point DatabaseManager at tmp data dir by monkeypatching _get_data_dir via URLs
    mgr = DatabaseManager(
        config_url=f"sqlite:///{data_dir / 'cmdarr_config.db'}",
        cache_url=f"sqlite:///{data_dir / 'cmdarr_cache.db'}",
        library_audit_url=f"sqlite:///{data_dir / 'cmdarr_library_audit.db'}",
        init_library_audit=True,
    )
    session = mgr.get_library_audit_session_sync()
    yield {
        "mgr": mgr,
        "session": session,
        "music": music,
        "f1": f1,
        "f2": f2,
    }
    session.close()


def test_resolve_under_root_rejects_traversal(tmp_path: Path):
    root = tmp_path / "music"
    root.mkdir()
    with pytest.raises(UnsafePathError):
        resolve_under_root(root, "../etc/passwd")
    with pytest.raises(UnsafePathError):
        resolve_under_root(root, "/etc/passwd")
    with pytest.raises(UnsafePathError):
        resolve_under_root(root, "Artist/../../etc/passwd")


def test_resolve_under_root_ok(tmp_path: Path):
    root = tmp_path / "music"
    target = root / "A" / "b.flac"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"x")
    resolved = resolve_under_root(root, "A/b.flac")
    assert resolved == target.resolve()


def test_inventory_new_changed_missing(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    f1 = audit_env["f1"]

    r1 = run_inventory(session, music, extensions=[".flac"])
    assert r1.status == "COMPLETED"
    assert r1.eligible_files_seen == 2
    assert r1.new_files == 2
    assert r1.missing_files == 0

    rows = session.query(LibraryAuditFile).all()
    assert len(rows) == 2
    assert all(r.analysis_state == "PENDING" for r in rows)

    # Unchanged second inventory
    r2 = run_inventory(session, music, extensions=[".flac"])
    assert r2.new_files == 0
    assert r2.changed_files == 0
    assert r2.missing_files == 0

    # Change one file
    st = f1.stat()
    os.utime(f1, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))
    # also bump size by rewriting
    sr = 44100
    t = np.linspace(0, 0.3, int(sr * 0.3), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    sf.write(str(f1), np.column_stack([tone, tone]), sr, format="FLAC", subtype="PCM_16")

    r3 = run_inventory(session, music, extensions=[".flac"])
    assert r3.changed_files == 1

    # Delete one file → missing after completed inventory
    f1.unlink()
    r4 = run_inventory(session, music, extensions=[".flac"])
    assert r4.missing_files == 1
    missing = session.query(LibraryAuditFile).filter(LibraryAuditFile.is_present.is_(False)).all()
    assert len(missing) == 1


def test_incomplete_inventory_does_not_mark_missing(audit_env, monkeypatch):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    assert (
        session.query(LibraryAuditFile).filter(LibraryAuditFile.is_present.is_(True)).count() == 2
    )

    # Force failure mid-walk by making rglob raise after first files processed via patched method
    original = Path.rglob

    def boom(self, pattern):
        raise RuntimeError("simulated walk failure")

    monkeypatch.setattr(Path, "rglob", boom)
    result = run_inventory(session, music, extensions=[".flac"])
    assert result.status == "FAILED"
    # Prior present rows must remain present
    assert (
        session.query(LibraryAuditFile).filter(LibraryAuditFile.is_present.is_(True)).count() == 2
    )
    monkeypatch.setattr(Path, "rglob", original)


def test_analysis_and_review_bind_to_content_hash(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    provider = FakeProvider(verdict="SUSPICIOUS", score=70)

    batch = run_analysis_batch(session, music, limit=10, provider=provider)
    assert batch.completed == 2
    assert batch.suspicious == 2
    assert len(provider.calls) == 2

    row = session.query(LibraryAuditFile).first()
    assert row.analysis_state == "ANALYZED"
    assert row.content_hash
    assert row.current_analysis_id
    assert row.artist == "Test Artist"

    review = create_review(session, row.id, "ACCEPTED", note="ok for now")
    assert review.disposition == "ACCEPTED"
    assert review.content_hash == row.content_hash
    session.refresh(row)
    assert row.current_review_id == review.id

    # Reanalyze queues and clears current review applicability on new analysis
    queue_reanalyze(session, row.id)
    session.refresh(row)
    assert row.analysis_state == "PENDING"

    provider2 = FakeProvider(verdict="AUTHENTIC", score=0)
    analyze_file(session, row, music, provider2)
    session.refresh(row)
    assert row.analysis_state == "ANALYZED"
    assert row.current_review_id is None  # new bytes/analysis clears current review pointer


def test_retention_deletes_old_missing(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    audit_env["f1"].unlink()
    run_inventory(session, music, extensions=[".flac"])

    missing = session.query(LibraryAuditFile).filter(LibraryAuditFile.is_present.is_(False)).one()
    missing.missing_since = datetime.now(UTC) - timedelta(days=120)
    session.commit()

    deleted = cleanup_missing_records(session, retention_days=90)
    assert deleted == 1
    assert session.query(LibraryAuditFile).count() == 1


def test_recover_stale_analyzing(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    row = session.query(LibraryAuditFile).first()
    row.analysis_state = "ANALYZING"
    row.analysis_queued_at = datetime.now(UTC) - timedelta(hours=2)
    row.updated_at = datetime.now(UTC) - timedelta(hours=2)
    session.commit()
    recovered = recover_stale_analyzing(session, stale_minutes=60)
    assert recovered == 1
    session.refresh(row)
    assert row.analysis_state == "PENDING"


def test_sha256_file(tmp_path: Path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_to_jsonable_numpy_bool():
    import numpy as np

    from services.library_audit.jsonutil import to_jsonable

    payload = {"has_dc_offset": np.bool_(True), "score": np.int64(12), "nested": [np.float64(1.5)]}
    out = to_jsonable(payload)
    assert out == {"has_dc_offset": True, "score": 12, "nested": [1.5]}
    import json

    json.dumps(out)  # must not raise


def test_inventory_marks_non_flac_unsupported(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    mp3 = music / "Artist" / "Album" / "03 - Track.mp3"
    mp3.write_bytes(b"ID3fake")

    from services.library_audit.formats import (
        DEFAULT_ANALYSIS_EXTENSIONS,
        DEFAULT_INVENTORY_EXTENSIONS,
    )

    result = run_inventory(
        session,
        music,
        extensions=DEFAULT_INVENTORY_EXTENSIONS,
        analysis_extensions=DEFAULT_ANALYSIS_EXTENSIONS,
    )
    assert result.status == "COMPLETED"
    assert result.eligible_files_seen == 3

    flacs = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".flac").all()
    assert all(r.analysis_state == "PENDING" for r in flacs)

    mp3_row = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".mp3").one()
    assert mp3_row.analysis_state == "UNSUPPORTED"

    from services.library_audit.service import select_pending_files

    pending = select_pending_files(session, limit=50)
    assert all(p.extension == ".flac" for p in pending)
    assert len(pending) == 2
