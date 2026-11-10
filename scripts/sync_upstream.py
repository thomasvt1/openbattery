"""Prepare an ancestry-preserving upstream PR from a disposable clean checkout.

No force pushes, automatic conflict resolutions, or automatic merges. Uses the
workflow's GITHUB_TOKEN through gh; no personal access token is required.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

UPSTREAM = "ffunes/Omnibattery"
BASE = "openbattery"
BRANCH_PREFIX = "codex/sync-upstream/"


def run(*args: str, cwd: Path | None = None, check: bool = True):
    return subprocess.run(args, cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8")


def git(repo: Path, *args: str, check: bool = True):
    return run("git", *args, cwd=repo, check=check)


def validate_ref(ref: str) -> str:
    """Accept a tag, branch or commit without allowing Git option/ref expressions."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", ref) or ".." in ref:
        raise ValueError("Use a plain upstream tag, branch or commit SHA")
    return ref


class MergeConflict(RuntimeError):
    def __init__(self, paths: list[str]):
        self.paths = paths
        super().__init__("Upstream merge requires manual resolution: " + ", ".join(paths))


def prepare_merge(repo: Path, base: str, target: str, branch: str) -> bool:
    """Merge into a new local branch; return False if already integrated."""
    if git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("Use a clean disposable checkout for upstream synchronization")
    ancestry = git(repo, "merge-base", "--is-ancestor", target, base, check=False)
    if ancestry.returncode == 0:
        return False
    if ancestry.returncode != 1:
        raise RuntimeError(ancestry.stderr)
    git(repo, "switch", "-c", branch, base)
    merged = git(repo, "merge", "--no-ff", "--no-edit", target, check=False)
    if merged.returncode:
        paths = git(repo, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        if git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False).returncode == 0:
            git(repo, "merge", "--abort")
        if paths:
            raise MergeConflict(paths)
        raise RuntimeError(merged.stderr or merged.stdout)
    return True


def report(message: str) -> None:
    print(message)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(message + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-ref", default="", help="Default: latest stable GitHub release")
    parser.add_argument("--dry-run", action="store_true", help="Merge locally only; never push or create a PR")
    args = parser.parse_args()
    repo = Path.cwd()
    repository = os.environ["GITHUB_REPOSITORY"]
    ref = args.upstream_ref or json.loads(run("gh", "api", f"repos/{UPSTREAM}/releases/latest").stdout)["tag_name"]
    ref = validate_ref(ref)
    git(repo, "fetch", "--no-tags", f"https://github.com/{UPSTREAM}.git", ref)
    target = git(repo, "rev-parse", "FETCH_HEAD^{commit}").stdout.strip()
    git(repo, "fetch", "origin", BASE)
    base = git(repo, "rev-parse", f"origin/{BASE}").stdout.strip()
    if git(repo, "merge-base", "--is-ancestor", target, base, check=False).returncode == 0:
        report(f"Already integrated: {UPSTREAM}@{ref} (`{target}`). No PR needed.")
        return
    prs = json.loads(run("gh", "pr", "list", "--repo", repository, "--state", "open", "--base", BASE,
                         "--json", "headRefName,url").stdout)
    pending = next((pr for pr in prs if pr["headRefName"].startswith(BRANCH_PREFIX)), None)
    if pending:
        report(f"An upstream sync PR is already open: {pending['url']}. Finish it before preparing another.")
        return
    branch = BRANCH_PREFIX + target[:12]
    try:
        prepare_merge(repo, base, target, branch)
    except MergeConflict as error:
        report("## Upstream sync needs manual resolution\n\n"
               f"Target: `{ref}` (`{target}`). No branch was pushed and no PR was created.\n\n"
               + "\n".join(f"- `{path}`" for path in error.paths)
               + "\n\nFollow UPSTREAM.md to resolve the merge in a dedicated branch.")
        raise
    record = repo / ".openbattery" / "upstream.json"
    record.parent.mkdir(exist_ok=True)
    record.write_text(json.dumps({"repository": UPSTREAM, "ref": ref, "commit": target}, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", ".openbattery/upstream.json")
    git(repo, "commit", "-m", f"Record upstream baseline {ref}")
    if args.dry_run:
        report(f"Dry run passed: merged `{ref}` into `{branch}`, preserving upstream ancestry. Nothing published.")
        return
    # An existing remote branch is never rewritten. A failed/non-fast-forward
    # push needs human inspection rather than discarding a previous resolution.
    git(repo, "push", "origin", f"HEAD:refs/heads/{branch}")
    body = (
        f"## Summary\n\nMerge [{UPSTREAM}@{ref}](https://github.com/{UPSTREAM}/commit/{target}) into OpenBattery.\n\n"
        "**Use Create a merge commit for this PR. Do not squash or rebase:** future syncs rely on upstream ancestry.\n\n"
        "## Validation\n\nReview changes to drivers, control logic, entity contracts, packaging and workflows. "
        "Run the unit, HA-flow, HACS, Hassfest and documentation checks, then validate the local simulated HA.\n\n"
        "GitHub may show **Approve workflows to run** for this bot-created PR. Approve those checks in the PR before merging; "
        "a clean Git merge is not validation. No automatic merge is configured.\n\n"
        "OpenBattery owns `frontend/openbattery/`; inspect upstream panel changes for features or fixes to port explicitly. "
        "See UPSTREAM.md for ownership and the review checklist.\n"
    )
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "body.md"
        path.write_text(body, encoding="utf-8")
        url = run("gh", "pr", "create", "--repo", repository, "--base", BASE, "--head", branch,
                  "--title", f"Sync OmniBattery {ref} into OpenBattery", "--body-file", str(path)).stdout.strip()
    report(f"Prepared {url}. Review and approve CI if requested; merge with a merge commit after validation.")


if __name__ == "__main__":
    main()
