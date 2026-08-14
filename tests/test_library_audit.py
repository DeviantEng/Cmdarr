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
    clear_current_review,
    create_review,
    effective_verdict,
    queue_reanalyze,
    reanalyze_file_now,
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

    review = create_review(session, row.id, "FALSE_POSITIVE", note="analyzer wrong")
    assert review.disposition == "FALSE_POSITIVE"
    assert review.content_hash == row.content_hash
    session.refresh(row)
    assert row.current_review_id == review.id

    # Same-bytes reanalyze keeps disposition; queue path still marks PENDING.
    queue_reanalyze(session, row.id)
    session.refresh(row)
    assert row.analysis_state == "PENDING"

    provider2 = FakeProvider(verdict="AUTHENTIC", score=0)
    analyze_file(session, row, music, provider2)
    session.refresh(row)
    assert row.analysis_state == "ANALYZED"
    assert row.current_review_id == review.id

    # Content change clears current disposition
    path = music / row.relative_path
    path.write_bytes(path.read_bytes() + b"\x00")
    analyze_file(session, row, music, provider2)
    session.refresh(row)
    assert row.current_review_id is None


def test_reanalyze_file_now_runs_immediately(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    row = session.query(LibraryAuditFile).first()
    provider = FakeProvider(verdict="WARNING", score=40)
    updated, analysis = reanalyze_file_now(session, row.id, music, provider=provider)
    assert analysis is not None
    assert analysis.verdict == "WARNING"
    assert updated.analysis_state == "ANALYZED"
    assert len(provider.calls) == 1


def test_clear_current_review(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    row = session.query(LibraryAuditFile).first()
    analyze_file(session, row, music, FakeProvider())
    create_review(session, row.id, "UNSURE", note="oops")
    session.refresh(row)
    assert row.current_review_id is not None
    clear_current_review(session, row.id)
    session.refresh(row)
    assert row.current_review_id is None


def test_create_review_maps_legacy_accepted(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    row = session.query(LibraryAuditFile).first()
    analyze_file(session, row, music, FakeProvider())
    review = create_review(session, row.id, "ACCEPTED")
    assert review.disposition == "FALSE_POSITIVE"


def test_false_positive_overrides_effective_verdict():
    assert effective_verdict("FAKE_CERTAIN", "FALSE_POSITIVE") == "AUTHENTIC"
    assert effective_verdict("FAKE_CERTAIN", "ACCEPTED") == "AUTHENTIC"
    assert effective_verdict("FAKE_CERTAIN", "IGNORE") == "FAKE_CERTAIN"
    assert effective_verdict("WARNING", None) == "WARNING"


def test_inventory_sets_parent_path_for_folder_select(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    run_inventory(session, music, extensions=[".flac"])
    rows = session.query(LibraryAuditFile).all()
    assert rows
    assert all(r.parent_path == "Artist/Album" for r in rows)


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


def test_inventory_marks_non_analyzable_unsupported(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    mp3 = music / "Artist" / "Album" / "03 - Track.mp3"
    wav = music / "Artist" / "Album" / "04 - Track.wav"
    mp3.write_bytes(b"ID3fake")
    wav.write_bytes(b"RIFFfake")

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
    assert result.eligible_files_seen == 4

    flacs = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".flac").all()
    assert all(r.analysis_state == "PENDING" for r in flacs)

    mp3_row = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".mp3").one()
    assert mp3_row.analysis_state == "PENDING"

    wav_row = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".wav").one()
    assert wav_row.analysis_state == "UNSUPPORTED"

    from services.library_audit.service import select_pending_files

    pending = select_pending_files(session, limit=50)
    assert {p.extension for p in pending} == {".flac", ".mp3"}
    assert len(pending) == 3


def test_inventory_requeues_unsupported_when_now_analyzable(audit_env):
    session = audit_env["session"]
    music = audit_env["music"]
    mp3 = music / "Artist" / "Album" / "03 - Track.mp3"
    mp3.write_bytes(b"ID3fake")

    from services.library_audit.formats import DEFAULT_INVENTORY_EXTENSIONS

    run_inventory(
        session,
        music,
        extensions=DEFAULT_INVENTORY_EXTENSIONS,
        analysis_extensions=[".flac"],
    )
    mp3_row = session.query(LibraryAuditFile).filter(LibraryAuditFile.extension == ".mp3").one()
    assert mp3_row.analysis_state == "UNSUPPORTED"

    run_inventory(
        session,
        music,
        extensions=DEFAULT_INVENTORY_EXTENSIONS,
        analysis_extensions=[".flac", ".mp3"],
    )
    session.refresh(mp3_row)
    assert mp3_row.analysis_state == "PENDING"


def test_composite_routes_mp3_and_flac(tmp_path: Path):
    class _P:
        def __init__(self, name: str):
            self.name = name
            self.calls: list[str] = []

        def health(self):
            return ProviderHealth(healthy=True, provider=self.name)

        def capabilities(self):
            return ProviderCapabilities(provider=self.name, extensions=[f".{self.name}"])

        def analyze(self, absolute_path: str, mode: str = "standard"):
            self.calls.append(absolute_path)
            return ProviderAnalysisResult(provider=self.name, verdict="AUTHENTIC", score=1)

    from services.library_audit.router import CompositeAnalyzerProvider

    flac_p = _P("flac")
    mp3_p = _P("mp3")
    comp = CompositeAnalyzerProvider(flac=flac_p, mp3=mp3_p)
    comp.analyze(str(tmp_path / "a.flac"))
    comp.analyze(str(tmp_path / "b.mp3"))
    assert flac_p.calls and flac_p.calls[0].endswith(".flac")
    assert mp3_p.calls and mp3_p.calls[0].endswith(".mp3")


def test_mp3_probe_on_synthetic_file(tmp_path: Path):
    """Encode a tiny MP3 with ffmpeg when available."""
    pytest.importorskip("mutagen")
    import shutil
    import subprocess

    from mutagen.mp3 import MP3

    out = tmp_path / "tone.mp3"
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not available to synthesize MP3")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.25",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "192k",
            str(out),
        ],
        check=True,
        capture_output=True,
    )

    from services.library_audit.mp3_probe import Mp3ProbeProvider

    result = Mp3ProbeProvider().analyze(str(out))
    assert result.provider == "mp3_probe"
    assert result.verdict in {"AUTHENTIC", "WARNING", "SUSPICIOUS", "INCONCLUSIVE"}
    assert result.evidence.get("bitrate_kbps") is not None
    assert MP3(out).info.bitrate > 0


def test_spectrum_curve_on_flac(audit_env):
    from services.library_audit.spectrum import compute_spectrum_curve

    curve = compute_spectrum_curve(audit_env["f1"], cutoff_hz=18000)
    assert curve is not None
    assert len(curve["freqs_hz"]) == len(curve["norm"]) >= 2
    assert curve["nyquist_hz"] > 0
    assert curve["cutoff_hz"] == 18000.0


def test_spectrum_resolve_under_root(audit_env):
    """Pieces used by GET /files/{id}/spectrum."""
    from services.library_audit.paths import resolve_under_root
    from services.library_audit.spectrum import compute_spectrum_curve

    abs_path = resolve_under_root(audit_env["music"], "Artist/Album/01 - Track.flac")
    curve = compute_spectrum_curve(abs_path)
    assert curve is not None
    assert curve["nyquist_hz"] == pytest.approx(22050.0)


def test_flac_triage_authentic(monkeypatch, audit_env):
    calls: list[tuple[float, bool]] = []

    class FakeAnalyzer:
        def __init__(self, sample_duration: float = 30.0, deep: bool = False):
            self.sample_duration = sample_duration
            self.deep = deep

        def analyze_file(self, path):
            calls.append((self.sample_duration, self.deep))
            return {"verdict": "AUTHENTIC", "score": 5, "cutoff_freq": 21000, "reason": "ok"}

    monkeypatch.setattr("flac_detective.FLACAnalyzer", FakeAnalyzer)
    from services.library_audit.flac_detective import FlacDetectiveProvider

    result = FlacDetectiveProvider().analyze(str(audit_env["f1"]), mode="triage")
    assert calls == [(20.0, False)]
    assert result.verdict == "AUTHENTIC"
    assert result.evidence.get("analysis_pass") == "triage"
    assert result.evidence.get("needs_deep") is False
    assert "spectrum_curve" not in result.evidence


def test_flac_triage_fake_is_provisional(monkeypatch, audit_env):
    calls: list[tuple[float, bool]] = []

    class FakeAnalyzer:
        def __init__(self, sample_duration: float = 30.0, deep: bool = False):
            self.sample_duration = sample_duration
            self.deep = deep

        def analyze_file(self, path):
            calls.append((self.sample_duration, self.deep))
            return {
                "verdict": "FAKE_CERTAIN",
                "score": 90,
                "cutoff_freq": 16000,
                "reason": "cassette rip suspected",
            }

    monkeypatch.setattr("flac_detective.FLACAnalyzer", FakeAnalyzer)
    from services.library_audit.flac_detective import FlacDetectiveProvider

    result = FlacDetectiveProvider().analyze(str(audit_env["f1"]), mode="triage")
    assert calls == [(20.0, False)]
    assert result.verdict == "WARNING"
    assert result.evidence.get("needs_deep") is True
    assert result.evidence.get("triage_verdict") == "FAKE_CERTAIN"
    assert result.evidence.get("fake_certain_promoted") is False
    assert "spectrum_curve" not in result.evidence


def test_flac_deep_promotes_fake_certain(monkeypatch, audit_env):
    calls: list[tuple[float, bool]] = []

    class FakeAnalyzer:
        def __init__(self, sample_duration: float = 30.0, deep: bool = False):
            self.sample_duration = sample_duration
            self.deep = deep

        def analyze_file(self, path):
            calls.append((self.sample_duration, self.deep))
            return {
                "verdict": "FAKE_CERTAIN",
                "score": 95,
                "cutoff_freq": 16000,
                "reason": "mp3 transcode signature",
                "estimated_mp3_bitrate": 192,
                "residual_floor_db": -72.0,
                "duration_real": 200.0,
            }

    monkeypatch.setattr("flac_detective.FLACAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "services.library_audit.flac_detective.compute_spectrum_curve",
        lambda path, cutoff_hz=None: {
            "freqs_hz": [0.0, 1000.0],
            "norm": [1.0, 0.5],
            "nyquist_hz": 22050.0,
            "cutoff_hz": cutoff_hz,
        },
    )
    from services.library_audit.flac_detective import FlacDetectiveProvider

    result = FlacDetectiveProvider().analyze(str(audit_env["f1"]), mode="deep")
    assert calls == [(60.0, True)]
    assert result.verdict == "FAKE_CERTAIN"
    assert result.evidence.get("fake_certain_promoted") is True
    assert result.evidence.get("spectrum_curve") is not None


def test_flac_deep_demotes_cassette_alone(monkeypatch, audit_env):
    class FakeAnalyzer:
        def __init__(self, sample_duration: float = 30.0, deep: bool = False):
            pass

        def analyze_file(self, path):
            return {
                "verdict": "FAKE_CERTAIN",
                "score": 90,
                "cutoff_freq": 15000,
                "reason": "cassette tape rip protection",
                "duration_real": 180.0,
            }

    monkeypatch.setattr("flac_detective.FLACAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "services.library_audit.flac_detective.compute_spectrum_curve",
        lambda path, cutoff_hz=None: None,
    )
    from services.library_audit.flac_detective import FlacDetectiveProvider

    result = FlacDetectiveProvider().analyze(str(audit_env["f1"]), mode="deep")
    assert result.verdict == "WARNING"
    assert result.evidence.get("fake_certain_blocked_reason") == "cassette_alone"
    assert result.evidence.get("fake_certain_promoted") is False


def test_flac_deep_demotes_short_track(monkeypatch, audit_env):
    class FakeAnalyzer:
        def __init__(self, sample_duration: float = 30.0, deep: bool = False):
            pass

        def analyze_file(self, path):
            return {
                "verdict": "FAKE_CERTAIN",
                "score": 90,
                "cutoff_freq": 16000,
                "reason": "mp3 transcode",
                "estimated_mp3_bitrate": 128,
                "residual_floor_db": -70.0,
                "duration_real": 4.0,
            }

    monkeypatch.setattr("flac_detective.FLACAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(
        "services.library_audit.flac_detective.compute_spectrum_curve",
        lambda path, cutoff_hz=None: None,
    )
    from services.library_audit.flac_detective import FlacDetectiveProvider

    result = FlacDetectiveProvider().analyze(str(audit_env["f1"]), mode="deep")
    assert result.verdict == "WARNING"
    assert result.evidence.get("fake_certain_blocked_reason") == "short_track"


def test_triage_batch_queues_pending_deep(audit_env):
    """Flagged triage results land in PENDING_DEEP, not Needs Review as Fake Certain."""

    class FlagProvider(FakeProvider):
        def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
            self.calls.append(absolute_path)
            return ProviderAnalysisResult(
                provider="fake",
                provider_version="0.0.1",
                provider_mode=mode,
                verdict="WARNING",
                score=90.0,
                summary="provisional",
                evidence={"needs_deep": True, "triage_verdict": "FAKE_CERTAIN"},
                raw_result={"verdict": "FAKE_CERTAIN"},
                metadata={},
            )

    session = audit_env["session"]
    run_inventory(
        session,
        audit_env["music"],
        extensions=[".flac"],
        analysis_extensions=[".flac"],
    )
    provider = FlagProvider()
    run_analysis_batch(
        session,
        audit_env["music"],
        limit=10,
        provider=provider,
        mode="triage",
        analysis_extensions=[".flac"],
    )
    rows = session.query(LibraryAuditFile).all()
    assert rows
    assert all(r.analysis_state == "PENDING_DEEP" for r in rows)
    assert all(r.current_analysis_id is not None for r in rows)


def test_prefer_triage_first_skips_deep_below_80(audit_env):
    from services.library_audit.service import (
        run_audit_cycle,
        should_run_deep_batch,
        triage_progress,
    )

    assert should_run_deep_batch(
        deep_batch_size=10,
        prefer_triage_first=True,
        triage_progress_pct=50.0,
    ) == (False, "triage_below_threshold")
    assert should_run_deep_batch(
        deep_batch_size=10,
        prefer_triage_first=True,
        triage_progress_pct=80.0,
    ) == (True, None)
    assert should_run_deep_batch(
        deep_batch_size=10,
        prefer_triage_first=False,
        triage_progress_pct=10.0,
    ) == (True, None)
    assert should_run_deep_batch(
        deep_batch_size=0,
        prefer_triage_first=False,
        triage_progress_pct=100.0,
    ) == (False, "deep_batch_size_zero")

    class FlagProvider(FakeProvider):
        def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
            self.calls.append(mode)
            if mode == "triage":
                return ProviderAnalysisResult(
                    provider="fake",
                    provider_version="0.0.1",
                    provider_mode=mode,
                    verdict="WARNING",
                    score=90.0,
                    evidence={"needs_deep": True},
                    raw_result={},
                    metadata={},
                )
            return ProviderAnalysisResult(
                provider="fake",
                provider_version="0.0.1",
                provider_mode=mode,
                verdict="SUSPICIOUS",
                score=70.0,
                evidence={"needs_deep": False},
                raw_result={},
                metadata={},
            )

    session = audit_env["session"]
    music = audit_env["music"]
    album = music / "Artist" / "Album"
    for i in range(10):
        path = album / f"{i:02d} - Extra.flac"
        if not path.exists():
            sr = 44100
            t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
            tone = (0.1 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
            sf.write(path, np.column_stack([tone, tone]), sr, format="FLAC")

    run_inventory(
        session,
        music,
        extensions=[".flac"],
        analysis_extensions=[".flac"],
    )
    provider = FlagProvider()
    # Triage only 1 file → progress stays well under 80% → deep skipped
    summary = run_audit_cycle(
        session,
        music,
        triage_batch_size=1,
        deep_batch_size=10,
        force_inventory=False,
        inventory_interval_hours=168,
        analysis_extensions=[".flac"],
        inventory_extensions=[".flac"],
        provider=provider,
        prefer_triage_first=True,
        deep_after_triage_pct=80.0,
    )
    assert summary.triage.attempted == 1
    assert summary.deep_skipped is True
    assert summary.deep_skip_reason == "triage_below_threshold"
    assert summary.deep.attempted == 0
    assert "deep" not in provider.calls
    pct, done, total = triage_progress(session, [".flac"])
    assert total >= 10
    assert pct < 80.0
    assert done >= 1


def test_legacy_provider_mode_standard_uses_triage_pipeline(audit_env):
    """Saved provider_mode=standard must not force deep-only (deep_batch_size) runs."""
    from services.library_audit.service import run_audit_cycle

    class CountingProvider(FakeProvider):
        def __init__(self):
            super().__init__(verdict="AUTHENTIC", score=5.0)
            self.modes: list[str] = []

        def analyze(self, absolute_path: str, mode: str = "standard") -> ProviderAnalysisResult:
            self.modes.append(mode)
            return super().analyze(absolute_path, mode=mode)

    session = audit_env["session"]
    run_inventory(
        session,
        audit_env["music"],
        extensions=[".flac"],
        analysis_extensions=[".flac"],
    )
    provider = CountingProvider()
    summary = run_audit_cycle(
        session,
        audit_env["music"],
        triage_batch_size=25,
        deep_batch_size=10,
        force_inventory=False,
        inventory_interval_hours=168,
        analysis_extensions=[".flac"],
        inventory_extensions=[".flac"],
        provider=provider,
        provider_mode="standard",
        prefer_triage_first=True,
        deep_after_triage_pct=80.0,
    )
    assert summary.triage.attempted >= 1
    assert all(m == "triage" for m in provider.modes)
    # Prefer triage first + fresh library → deep skipped after triage clears authentic
    assert (
        summary.deep.attempted == 0 or summary.deep_skipped or summary.triage_progress_pct >= 80.0
    )


def test_sort_file_items_folder_pending_deep_and_score():
    from app.api.library_audit import _attach_folder_stats, _sort_file_items

    items = [
        {
            "relative_path": "B/2.flac",
            "parent_path": "B",
            "analysis": {"verdict": "WARNING", "score": 10},
            "analysis_state": "PENDING_DEEP",
            "review": None,
        },
        {
            "relative_path": "A/1.flac",
            "parent_path": "A",
            "analysis": {"verdict": "FAKE_CERTAIN", "score": 90},
            "analysis_state": "ANALYZED",
            "review": None,
        },
        {
            "relative_path": "A/2.flac",
            "parent_path": "A",
            "analysis": {"verdict": "WARNING", "score": None},
            "analysis_state": "PENDING_DEEP",
            "review": None,
        },
        {
            "relative_path": "C/1.flac",
            "parent_path": "C",
            "analysis": {"verdict": "SUSPICIOUS", "score": 50},
            "analysis_state": "PENDING_DEEP",
            "review": None,
        },
    ]
    _attach_folder_stats(
        items,
        {
            "A": {"present_count": 10, "pending_deep_count": 10},
            "B": {"present_count": 12, "pending_deep_count": 1},
            "C": {"present_count": 8, "pending_deep_count": 8},
        },
    )
    _sort_file_items(items, sort_by="folder_pending_deep", sort_dir="desc")
    assert [i["parent_path"] for i in items] == ["A", "A", "C", "B"]

    _sort_file_items(items, sort_by="verdict", sort_dir="asc")
    assert items[0]["analysis"]["verdict"] == "FAKE_CERTAIN"

    _sort_file_items(items, sort_by="score", sort_dir="desc")
    assert items[0]["analysis"]["score"] == 90
    assert items[-1]["analysis"]["score"] is None
