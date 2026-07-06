"""Output summary for New Releases Discovery command executions."""

from services.command_executor import CommandExecutor


def _nrd_summary(stats: dict, duration: float = 12.3) -> str:
    return CommandExecutor()._build_new_releases_summary(stats, duration)


def test_nrd_summary_without_validation():
    summary = _nrd_summary({"artists_scanned": 25, "new_releases_detected": 2})
    assert summary == (
        "New Releases Discovery completed in 12.3s • "
        "Scanned 25 artists, 2 new release(s) detected"
    )


def test_nrd_summary_with_validation_and_scan():
    summary = _nrd_summary(
        {
            "validation_checked": 50,
            "validation_removed": 3,
            "artists_scanned": 25,
            "new_releases_detected": 0,
        }
    )
    assert summary == (
        "New Releases Discovery completed in 12.3s • "
        "Validated 50 pending/dismissed release(s), removed 3 already in MusicBrainz • "
        "Scanned 25 artists, no new releases detected"
    )


def test_nrd_summary_validation_only_no_artists():
    summary = _nrd_summary(
        {
            "validation_checked": 10,
            "validation_removed": 0,
            "artists_scanned": 0,
            "new_releases_detected": 0,
        }
    )
    assert summary == (
        "New Releases Discovery completed in 12.3s • "
        "Validated 10 pending/dismissed release(s), removed 0 already in MusicBrainz • "
        "No artists to scan"
    )
