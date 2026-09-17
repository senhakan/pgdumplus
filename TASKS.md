# Execution tracker

Updated: 2026-09-17. Specification: [PLAN.md](PLAN.md).
Statuses: READY, IN_PROGRESS, BLOCKED (dependency stated), DONE (evidence required).

## Verified baseline

- Canonical repo senhakan/pgdumpplus; command pg_dumpplus.
- Main baseline f3285c3; latest published release v1.2.0 at inspection.
- [CI 35253870996](https://github.com/senhakan/pgdumpplus/actions/runs/35253870996): success.
- Patcher safety, compiled packages, PG13/17 roundtrips and package smoke tests exist.
- New presets are on main after v1.2.0; not yet part of a newer stable release.
- Strict masks, dry-run, profiles and deterministic pseudonyms are not implemented.
- This tracker supersedes stale defect/completion claims in the previous list.

## Work queue

| ID | Status | Dependencies | Deliverable (PLAN section) |
| --- | --- | --- | --- |
| A1 | DONE | — | Strict masks and regression coverage (A1); local PG17.5 and CI PG13/17 checks pass |
| A2 | READY | A1 | Catalog-only dry-run and JSON schema (A2) |
| A3 | READY | A1 | Type/format/partition/snapshot/upstream coverage (A3) |
| B1 | READY | — | Version manifest, supported bases, package identity/order (B1) |
| B2 | READY | — | Source hashes, CI permissions, SBOM/provenance (B2) |
| B3 | BLOCKED | A1, A2, A3, B1, B2, D3a | Verified v2.0 candidate/stable promotion (B3) |
| C1 | BLOCKED | A2 | Compiled profile reader and tested examples (C1) |
| C2-design | BLOCKED | A3 | Key/type/execution design and review (C2-design) |
| C2 | BLOCKED | C1, C2-design | Typed deterministic pseudonyms (C2) |
| D1-linux | BLOCKED | B1, B2 | Native Linux ARM64 packages (D1) |
| D1-macos | BLOCKED | D1-linux | macOS packages and Homebrew tap (D1) |
| D2-local | BLOCKED | B1, B2 | Signed APT/RPM metadata and local client tests (D2) |
| D2-public | BLOCKED | D2-local, B3, hosting/key decision | Hosted channels and upgrades (D2) |
| D3a | READY | — | Accurate README/TR, matrix, changelog, contribution/security docs (D3) |
| D3b | BLOCKED | B3 | Release-binary demo/tutorials and launch drafts (D3) |
| CLEAN1 | READY | — | Audit and retire unsafe/redundant legacy entry points |

CLEAN1: inspect demo_setup.sql, mask_verify_ci.sh and verify_pgdumpplus.sh.
Migrate unique useful coverage to verify_isolated.py before removing scripts;
update references. Do not execute destructive legacy scripts on a live server.

## Release boundaries

1. v2.0: A1–A3, B1–B3, D3a. Strict masking is a breaking behavior change.
2. Later minor releases: C1, then C2 after architecture and runtime evidence.
3. D1/D2 each ship only after their own platform/channel gates pass.
4. D3b demonstrates an actual release, not unreleased functionality.

These are target milestones, not published versions or calendar promises.

## Evidence ledger

| Task | Commit/run | Observed result | Limits |
| --- | --- | --- | --- |
| Baseline | f3285c3 / 35253870996 | CI success | Existing matrix only |
| Planning | Working tree, 2026-09-17 | Plan and agent handoff created | No implementation or release performed |
| A1 local | 0ba5cf8 working tree | PG17.5 candidate build + isolated suite: 40 passed | CI evidence recorded below |
| A1 CI | [35256202241](https://github.com/senhakan/pgdumpplus/actions/runs/35256202241) | PG13/17 builds, 40-check integration suites and package smoke jobs passed | Release publication remains a separate B3 gate |

Add exact checked commit, CI URL or command and actual outcome for each task.
Never infer a test count or mark an ongoing run passed. Keep private evidence
outside Git; put only sanitized conclusions here.

## Resume instructions

First task: A1. Read MASK_VALIDATE_C and its injection points in
scripts/apply_pgdumpplus.py. Read skipped_mask and error tests in
scripts/verify_isolated.py. Reproduce warning/continue behavior with a synthetic
disposable fixture. Trace validation timing relative to table-data output,
then implement strict resolution and format/parallel regression checks.

A1 has no known external blocker. D2-public needs hosting/key ownership.
C2 needs a reviewed architecture before key-handling implementation.
At interruption record active task, changed paths, last test/result, exact next
action and unresolved blocker. PLAN.md contains the required behavior contract.
