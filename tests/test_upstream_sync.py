"""Exercise real Git merges without GitHub or network access."""
from pathlib import Path

import pytest

from scripts.sync_upstream import MergeConflict, git, prepare_merge, validate_ref


@pytest.fixture
def history(tmp_path):
    git(tmp_path, "init", "-b", "base")
    git(tmp_path, "config", "user.name", "Sync test")
    git(tmp_path, "config", "user.email", "sync@example.invalid")
    (tmp_path / "shared.txt").write_text("baseline\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Base")
    base = git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    git(tmp_path, "switch", "-c", "upstream")
    (tmp_path / "driver.txt").write_text("upstream driver fix\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Upstream fix")
    upstream = git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    git(tmp_path, "switch", "-c", "openbattery", base)
    (tmp_path / "panel.txt").write_text("OpenBattery panel\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Fork panel")
    return tmp_path, upstream


def test_sync_keeps_fork_changes_and_upstream_ancestry(history):
    repo, upstream = history
    assert prepare_merge(repo, "openbattery", upstream, "sync-test") is True
    assert (repo / "driver.txt").read_text() == "upstream driver fix\n"
    assert (repo / "panel.txt").read_text() == "OpenBattery panel\n"
    assert git(repo, "merge-base", "--is-ancestor", upstream, "HEAD").returncode == 0
    assert len(git(repo, "show", "-s", "--format=%P", "HEAD").stdout.split()) == 2
    assert prepare_merge(repo, "HEAD", upstream, "unused") is False


def test_conflict_aborts_without_dropping_fork_changes(history):
    repo, _ = history
    git(repo, "switch", "upstream")
    (repo / "shared.txt").write_text("upstream edit\n")
    git(repo, "commit", "-am", "Upstream conflicting edit")
    upstream = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "switch", "openbattery")
    (repo / "shared.txt").write_text("fork edit\n")
    git(repo, "commit", "-am", "Fork conflicting edit")
    before = git(repo, "rev-parse", "HEAD").stdout.strip()
    with pytest.raises(MergeConflict) as caught:
        prepare_merge(repo, "openbattery", upstream, "sync-test")
    assert caught.value.paths == ["shared.txt"]
    assert git(repo, "rev-parse", "HEAD").stdout.strip() == before
    assert (repo / "shared.txt").read_text() == "fork edit\n"
    assert not git(repo, "status", "--porcelain").stdout.strip()
    assert not (repo / ".git/MERGE_HEAD").exists()


def test_dirty_checkout_is_not_modified(history):
    repo, upstream = history
    (repo / "shared.txt").write_text("unsaved work\n")
    with pytest.raises(RuntimeError, match="clean disposable"):
        prepare_merge(repo, "openbattery", upstream, "sync-test")
    assert (repo / "shared.txt").read_text() == "unsaved work\n"
    assert git(repo, "branch", "--show-current").stdout.strip() == "openbattery"


@pytest.mark.parametrize("ref", ["v1.6.0", "main", "release/1.7", "bba9f226"])
def test_normal_refs_are_accepted(ref):
    assert validate_ref(ref) == ref


@pytest.mark.parametrize("ref", ["--upload-pack=bad", "HEAD^{commit}", "a..b", "main; command", "", "a\nb"])
def test_ref_options_and_expressions_are_rejected(ref):
    with pytest.raises(ValueError):
        validate_ref(ref)
