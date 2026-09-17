# pg_dumpplus development plan

## Product

A separately installed PostgreSQL command-line client with the familiar
`pg_dump` workflow plus row filtering and column masking. Users install a
compiled package; Python is only needed to build from source.

## Working rules

- Keep public documentation focused on installation and use.
- Keep credentials, server addresses and environment reports outside Git.
- Preserve existing databases, installed packages and server configuration.
- Use synthetic data in uniquely named databases for integration checks.
- Record observed failures before changing behavior; verify fixes by restoring
  dumps and comparing actual values, not only command exit codes.
- Make small changes with an explicit rollback path. Validate candidate builds
  in a separate directory before replacing an installed package.
- Do not describe a feature as verified on a platform that has not been checked.

## Milestones

### 1. Establish a reliable baseline

Inventory the designated test system. Create a repeatable integration suite
covering filtering, masking, restores, errors and ordinary unfiltered dumps.
Capture edge cases separately from the basic feature checks. Tests must create
their own databases and only remove resources created by that run.

Exit: results are recorded and reproducible; existing databases are unchanged.

### 2. Harden data handling

Address failed cases for quoted identifiers, NULL and short values, repeated
filters/masks, partitions and generated columns. Define what happens when a
mask cannot be applied. Check restore compatibility and foreign key behavior.
Make patch application repeatable and ensure anchor failures do not leave a
partially modified source tree.

Exit: fixed cases have regression coverage on supported PostgreSQL majors.

### 3. Deliver a focused client package

Build only the required client components. Stage installation with `DESTDIR`
instead of installing into the build host. Include `pg_dumpplus`, required
runtime libraries and the license; define the companion restore-tool policy.
Provide a versioned command available on PATH, with a predictable default when
multiple majors are installed. Preserve system PostgreSQL tools.

Unify tarball layouts, detect native library dependencies, and produce patches
from source files only. Avoid artifact filename collisions across distributions.

Exit: install, execute, upgrade and remove the candidate package without
changing the PostgreSQL service or existing clients.

### 4. Automate release validation

Run integration checks on pull requests and code changes for every supported
major. Gate releases on verification and package smoke checks. Generate a
single checksum manifest from the final assets. Add upstream regression checks
and compatibility coverage where practical.

Exit: a release cannot be published with a failed required check.

### 5. Publish and maintain

Keep English and Turkish usage guides consistent with actual releases. Publish
concise release notes, accurate platform support and reproducible examples.
Expand supported versions only after their build and restore checks pass.

## Tracking

See [TASKS.md](TASKS.md) for current status. Private execution reports live under
the Git-ignored `.local/` directory. A completed milestone does not imply the
remaining milestones are complete.
