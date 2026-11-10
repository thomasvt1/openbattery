# Keeping OpenBattery in sync

OpenBattery's default branch is `openbattery`. `upstream` points to
`https://github.com/ffunes/Omnibattery.git`; `origin` points to this fork.
The old fork's `main` branch is preserved and is not the integration branch.
The last incorporated upstream revision is recorded in `.openbattery/upstream.json`.

## Automated preparation

**Prepare upstream sync** checks the latest stable upstream GitHub release daily
at 05:13 UTC. It does nothing when that revision is already an ancestor of
OpenBattery. It creates at most one open sync PR at a time.

Actions → Prepare upstream sync → Run workflow also accepts a tag, branch or SHA.
Use `main` deliberately for unreleased fixes. The dry-run option rehearses the
merge in the disposable runner without pushing or opening a PR.

The workflow uses the repository's `GITHUB_TOKEN`, with contents and pull-request
write permission. Repository Actions settings must allow Actions to create pull
requests. No personal access token is needed. GitHub may require a maintainer to
click **Approve workflows to run** on a bot-created PR before CI starts; do not
interpret absent checks as passing checks.

Clean merges become `codex/sync-upstream/<upstream-sha>` PRs. Conflicts stop the
workflow, abort the local merge and list the affected paths in the run summary.
Nothing is force-pushed, automatically resolved or automatically merged. If a
push succeeded but PR creation failed, inspect that branch and open its PR
manually; the workflow will not overwrite an existing branch's resolutions.

## Merge procedure

1. Review the upstream diff, particularly drivers, battery control, configuration
   migrations, entity attributes/services, dependencies and GitHub workflows.
2. Resolve conflicts on a dedicated branch. Keep fork features explicitly; do
   not apply blanket `ours`/`theirs` resolutions or force-sync the default branch.
3. Run unit tests, HA flow tests, HACS, Hassfest and the strict documentation build.
4. Exercise the isolated local HA: grid control, monthly schedules, phase
   monitoring, unavailable/stale data and existing installation compatibility.
5. **Use Create a merge commit. Never squash or rebase an upstream-sync PR.**
   The upstream commits must remain ancestors so the next sync knows what was
   already incorporated. Ordinary feature PRs do not have this restriction.
6. Verify `.openbattery/upstream.json` records the incorporated SHA, and inspect
   upstream frontend changes for fixes/features to port to our panel.

For recurring manual conflicts, opt into `git config rerere.enabled true` in your
clone. Review reused resolutions; they are not a substitute for tests.

## Ownership

| Files | Policy |
|---|---|
| Drivers, control, pricing and HA entity contracts | Stay close to upstream; add focused feature modules and small explicit hooks |
| `frontend/marstek-panel.js` and its original scene assets | Upstream-owned reference; accept reviewed upstream changes, do not redesign here |
| `frontend/openbattery/` | OpenBattery-owned panel and assets; port upstream UI fixes deliberately |
| `openbattery_brand.py` | Fork-owned panel identity and entry point |
| `.openbattery/`, sync script/workflow, `UPSTREAM.md` | Fork-owned maintenance policy |
| README, manifest, HACS, documentation branding | Fork-specific identity; preserve upstream attribution |

The original panel is not registered by OpenBattery. The active panel uses a
distinct custom-element name and its own asset paths. Its HA domain, storage,
service names, entity IDs and sidebar URL remain unchanged. This separation
reduces UI conflicts; it does not promise conflict-free backend merges.

## Frontend tests

Existing frontend tests now target the shipped `frontend/openbattery/panel.js`.
When importing new upstream frontend tests, decide whether the behavior applies
to our UI and point the test at the active panel when porting the corresponding
change. Tests accidentally aimed at the inactive upstream panel do not validate
OpenBattery. Browser smoke tests must verify the registered `openbattery-panel`,
the logo/scene assets and the existing controls at `/omnibattery`.
