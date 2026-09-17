# Work list

Updated: 2026-09-17. Status reflects observed results, not planned capability.

## P0 — Baseline and correctness

- [x] Review patcher, packaging, verification scripts and workflows.
- [x] Rewrite English and Turkish user documentation.
- [x] Inventory the designated test host without modifying existing databases.
- [x] Add and run isolated integration checks on the installed PG17 client.
- [x] Record unfiltered comparison against the matching upstream client.
- [x] Check custom, plain SQL, INSERT and parallel directory restore paths on PG13/17.
- [x] Verify quoted column names, NULLs and short mask inputs on PG13/17.
- [x] Fix the four observed data-handling defects; each candidate passes 28 checks.
- [ ] Define strict failure behavior for masks that cannot be applied.
- [ ] Make the patcher safe on anchor failure and older patched source trees.
- [x] Verify PG13 with an isolated PG13.18 server: 28 checks passed.

## P1 — Standalone packages

- [x] Share client-only build/staging logic between RPM and DEB.
- [x] Remove host installation and broad deletion from packaging scripts.
- [x] Define PATH commands and coexistence of multiple major versions.
- [x] Generate runtime dependencies and include the license.
- [x] Unify tarball paths and source-only patch generation.
- [x] Eliminate cross-platform patch asset collisions.
- [x] Validate isolated install, upgrade and removal of candidate RPM/DEB.
- [x] Confirm PostgreSQL service and existing client binaries are unchanged.

## P1 — Automated verification

- [x] Replace CI hard-coded test database names and inconsistent fixtures with
  the isolated verification suite. Legacy standalone scripts remain to retire.
- [ ] Fix legacy demo SQL: connected-database deletion and oversized ID values.
- [x] Configure the new suite on code changes and pull requests for both supported
  majors. Remote GitHub execution remains to be observed after publishing changes.
- [x] Make successful verification a prerequisite for release publication in CI.
- [ ] Validate release archives and checksum coverage.

## P2 — Compatibility and publication

- [ ] Cover partitions, schema selection, repeated patterns and concurrent writes.
- [ ] Run upstream pg_dump regression checks for candidate builds.
- [ ] Review supported PostgreSQL versions and dependency security before release.
- [ ] Synchronize documentation with the final package layout and mask semantics.
- [ ] Prepare release notes and publish only verified artifacts.

## Known issues from source review

- Baseline execution found an older installed PG17 package without `--mask`;
  candidate source builds must be checked independently of installed packages.
- Invalid mask columns currently warn and continue; data can remain unmasked.
- The current CI fixture uses `adres`, while some checks reference `address`.
- Some mask expectations do not match the generated data or SQL projection.
- DEB patch generation includes the compiled tree, and patch asset names collide
  when artifacts from different distributions are merged.
- Builds currently install more than a focused dump client needs.
- A legacy bundled psql could not load its readline library on the test OS;
  native runtime dependencies need explicit package verification.
- The current public release still contains the older package layout; the new
  client-only artifacts need a new release after CI passes.

## Latest verification

2026-09-17: clean candidate builds on PostgreSQL 17.8 and 13.18 each pass
28 dump/restore checks. Four reproduced bugs were corrected: masked INSERT
column names, quoted mask identifiers, NULL handling in `all`, and short-value
handling in `tc`. No installed client was replaced. Candidate packaging,
upgrade/removal validation and execution of the revised GitHub workflows are
still outstanding. Patcher safety and focused client package smoke tests are now
implemented. RPM and Ubuntu 24.04 DEB install/upgrade/run/remove smoke tests
passed without compiler tools; release archive/checksum validation and remote CI
execution remain before publication.
