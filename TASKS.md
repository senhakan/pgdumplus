# Execution tracker

Updated: 2026-09-17. Specification: [PLAN.md](PLAN.md).
Statuses: READY, IN_PROGRESS, BLOCKED (dependency stated), DONE (evidence required).

## Verified baseline

- Canonical repo senhakan/pgdumpplus; command pg_dumpplus.
- Main baseline f3285c3; latest published release v1.2.0 at inspection.
- [CI 35253870996](https://github.com/senhakan/pgdumpplus/actions/runs/35253870996): success.
- Patcher safety, compiled packages, PG13/17 roundtrips and package smoke tests exist.
- New presets are on main after v1.2.0; not yet part of a newer stable release.
- Strict masks and catalog-only dry-run are implemented and covered by CI.
  Profiles and deterministic pseudonyms remain unimplemented by design.
- This tracker supersedes stale defect/completion claims in the previous list.

## Work queue

| ID | Status | Dependencies | Deliverable (PLAN section) |
| --- | --- | --- | --- |
| A1 | DONE | — | Strict masks and regression coverage (A1); local PG17.5 and CI PG13/17 checks pass |
| A2 | DONE | A1 | Catalog-only dry-run and JSON schema (A2) |
| A3 | IN_PROGRESS | A1 | Type/format/partition/snapshot/upstream coverage (A3) |
| B1 | DONE | — | Version manifest, supported bases, package identity/order and cross-major guard (B1) |
| B2 | DONE | — | Source hashes, CI permissions, SBOM/provenance (B2) |
| B3 | BLOCKED | A1, A2, A3, B1, B2, D3a | Verified v2.0 candidate/stable promotion (B3) |
| C1 | BLOCKED | A2 | Compiled profile reader and tested examples (C1) |
| C2-design | IN_PROGRESS | A3 | Key/type/execution design and review in `docs/design/pseudonymization.md` (C2-design) |
| C2 | BLOCKED | C1, C2-design | Typed deterministic pseudonyms (C2) |
| D1-linux | BLOCKED | B1, B2 | Native Linux ARM64 packages (D1) |
| D1-macos | BLOCKED | D1-linux | macOS packages and Homebrew tap (D1) |
| D2-local | BLOCKED | B1, B2 | Signed APT/RPM metadata and local client tests (D2) |
| D2-public | BLOCKED | D2-local, B3, hosting/key decision | Hosted channels and upgrades (D2) |
| D3a | DONE | — | Accurate README/TR, matrix, changelog, contribution/security docs (D3) |
| D3b | BLOCKED | B3 | Release-binary demo/tutorials and launch drafts (D3) |
| CLEAN1 | DONE | — | Audit and retire unsafe/redundant legacy entry points |

CLEAN1: completed. Destructive and superseded shell scripts were removed after
their useful coverage was consolidated in `verify_isolated.py`; no repository
references remain.

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
| A1 local | a80188d | PG17.5 candidate build + isolated suite: 40 passed; patcher/idempotence checks passed | Strict validation is fail-fast |
| A1 CI | [35260089452](https://github.com/senhakan/pgdumpplus/actions/runs/35260089452) | PG13/17 builds, isolated verification and DEB/RPM smoke jobs passed | Release publication remains a separate B3 gate |
| A2 CI | [35264310934](https://github.com/senhakan/pgdumpplus/actions/runs/35264310934) | Dry-run text/JSON checks plus PG13/17 builds and package smoke jobs passed | Superseded by newer coverage below |
| A2 escaping CI | [35266116755](https://github.com/senhakan/pgdumpplus/actions/runs/35266116755) | JSON identifier escaping test, PG13/17 builds and package smoke jobs passed | Superseded by latest full matrix |
| Current CI | [35267465415](https://github.com/senhakan/pgdumpplus/actions/runs/35267465415) | All PG13/17 build, verify, DEB and RPM smoke jobs passed | Release-only attestation runs on a version tag |
| CLEAN1 | 1b79a32 + local audit | Retired destructive/redundant legacy scripts; consolidated verification remains in `verify_isolated.py` | Historical private test environments are intentionally not reproduced |
| Latest CI | [35269564040](https://github.com/senhakan/pgdumpplus/actions/runs/35269564040) | Commit dd8b81e: PG13/17 builds, isolated verification, DEB/RPM smoke jobs all passed | Release publication and provenance remain tag-only B3 gates |
| D3a | 035371e | Public README, Turkish guide, contribution guidance, security policy and issue templates reviewed; keyword stuffing and unqualified privacy claims removed | Release-binary tutorials and launch drafts wait for B3 |
| B1 source refresh | local + support-matrix.json | PostgreSQL 13.23 (legacy), 17.11 and 18.6 source hashes recorded; PG18.6 patcher clean/idempotence checks passed | Matrix result is recorded in the current-matrix row |
| B1 current matrix | [35270331753](https://github.com/senhakan/pgdumpplus/actions/runs/35270331753) | Commit 30f45cf: PG13.23/17.11/18.6 builds, isolated dump/restore, all DEB/RPM smoke jobs passed | Project-version-only upgrade ordering and release promotion remain B1/B3 work |
| B2 action pinning | 4fcdeae | All third-party workflow actions are pinned to reviewed immutable commit SHAs; Dependabot remains configured for update proposals | Release attestation itself is exercised only by a real candidate tag |
| A2 final | [35270987562](https://github.com/senhakan/pgdumpplus/actions/runs/35270987562) | Commit fc754c3: dry-run text/JSON, identifier escaping, custom-SQL non-execution and option error checks passed across PG13.23/17.11/18.6; all package smoke jobs passed | Custom expressions are reported, not fully type/runtime evaluated in dry-run |
| B1 package metadata fix | 25c1669 + local PG18.6 build | PG18’s changed schema-only option representation is handled conditionally; local DEB metadata reports project 1.2.0 and upstream 18.6 separately | Full matrix result is recorded below |
| Latest compatibility CI | [35272617138](https://github.com/senhakan/pgdumpplus/actions/runs/35272617138) | Commit 42b8543: PG13.23/17.11/18.6 builds, verify jobs, all DEB/RPM smoke jobs passed after PG18 fix | Release job skipped because no tag was created |
| Latest docs CI | [35273077003](https://github.com/senhakan/pgdumpplus/actions/runs/35273077003) | Commit 54f26f8: current PG13.23/17.11/18.6 build, verify and package smoke matrix passed | Release job skipped because no tag was created |
| Latest CI | [35273364265](https://github.com/senhakan/pgdumpplus/actions/runs/35273364265) | Commit ec35514: immutable-action workflow, PG13.23/17.11/18.6 build, verify and all DEB/RPM smoke jobs passed | Release job skipped because no tag was created |
| A3 domain/Unicode CI | [35278380212](https://github.com/senhakan/pgdumpplus/actions/runs/35278380212) | Commit 27b285e: text-domain custom cast, Unicode value, strict domain preset rejection and full PG13.23/17.11/18.6 matrix passed | Broader snapshot-concurrency and upstream regression evidence remains |
| A3 snapshot CI | [35279332809](https://github.com/senhakan/pgdumpplus/actions/runs/35279332809) | Commit 839f8b5: concurrent committed update during delayed export restored as one consistent snapshot across PG13.23/17.11/18.6 | Full upstream regression suite remains outside client-only build; cross-format snapshot tests continue |
| Latest CI | [35278650592](https://github.com/senhakan/pgdumpplus/actions/runs/35278650592) | Commit 3df6272: documentation evidence update plus full PG13.23/17.11/18.6 build, verify and package smoke matrix passed | Release publication remains blocked by open A3/B1 gates |
| B2 provenance dispatch | [35275197819](https://github.com/senhakan/pgdumpplus/actions/runs/35275197819) | Tagless dispatch passed full matrix, SBOM generation, tampered-file checksum rejection, asset attestations and `gh attestation verify` for every asset | No release was published; candidate/stable promotion remains B3 |
| A3 format/upstream comparison | [35280543186](https://github.com/senhakan/pgdumpplus/actions/runs/35280543186) | Commit b59f6e1: vanilla-vs-pgdumpplus plain and schema-only output comparison, plus concurrent snapshot checks for plain, custom and directory formats; PG13.23/17.11/18.6 matrix and package smoke tests passed | Full PostgreSQL upstream TAP/regression suite is outside this client-only verification; A3 remains open for that external coverage |
| B1 build identity | [35281659213](https://github.com/senhakan/pgdumpplus/actions/runs/35281659213) | Commit 23d9027: `--build-info` reports project SemVer, upstream PostgreSQL version and source commit; runtime-only DEB/RPM smoke tests and PG13.23/17.11/18.6 matrix passed | Upgrade ordering is covered by the later B1 package-upgrade row |
| B1 package upgrade ordering | [35283866146](https://github.com/senhakan/pgdumpplus/actions/runs/35283866146) | Commit ded0ded: DEB metadata fixture and separately built lower-project-version RPM fixture upgraded to the current package in runtime-only containers; install, version change, build identity, binary checks and removal passed across the verified matrix | DEB fixture keeps current binary identity because it tests package-manager ordering only; a release candidate still requires B3 gates |
| B1 cross-major guard | [35286844662](https://github.com/senhakan/pgdumpplus/actions/runs/35286844662) | Commit c4891d5: verify workflow connects the PG17 client to an isolated PG18.6 service and confirms PostgreSQL’s real `server version mismatch` refusal before export; full matrix passed | The guard is supplied by the matching upstream client path; B1 still awaits only final release-gate review |
| Public audit | [35287648751](https://github.com/senhakan/pgdumpplus/actions/runs/35287648751) | Commit 1f36ee9: tracked-file audit rejects credential, private-key and private-network markers; local and CI checks passed | Pattern scan complements, but does not replace, GitHub secret scanning |

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
