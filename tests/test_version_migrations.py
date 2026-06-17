"""Unit tests for version migration runner helpers."""

from database.version_migrations import VersionMigration, VersionMigrationRunner


def test_applicable_versions_includes_dev_base():
    runner = VersionMigrationRunner(config_db_path="/tmp/nonexistent-test.db")
    runner.current_version = "0.3.16-dev"
    assert runner._applicable_versions() == ["0.3.16-dev", "0.3.16"]


def test_applicable_versions_release_only():
    runner = VersionMigrationRunner(config_db_path="/tmp/nonexistent-test.db")
    runner.current_version = "0.3.16"
    assert runner._applicable_versions() == ["0.3.16"]


def test_migration_applies_for_dev_and_base_tags():
    runner = VersionMigrationRunner(config_db_path="/tmp/nonexistent-test.db")
    runner.current_version = "0.3.16-dev"
    dev_only = VersionMigration("0.3.16-dev", "x", "d", lambda c: None)
    release = VersionMigration("0.3.16", "y", "d", lambda c: None)
    other = VersionMigration("0.3.14", "z", "d", lambda c: None)
    assert runner._migration_applies(dev_only) is True
    assert runner._migration_applies(release) is True
    assert runner._migration_applies(other) is False
