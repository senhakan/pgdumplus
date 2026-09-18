# Deterministic pseudonymization design

This document defines the security boundary for a future typed pseudonymization
feature. It is a design constraint, not a claim that the feature is available.

## Threat model

The output may be shared with analysts who must join records without seeing the
original identifier. Pseudonyms are not encryption and do not protect low-
entropy values from guessing. The implementation must not expose the key in
command lines, profile files, generated SQL, dump metadata, logs or attestations.

## Execution and canonicalization

The client derives a canonical byte representation from the database value and
performs a reviewed keyed primitive locally. The server receives only the
resulting expression/value; the secret never crosses the connection. NULL stays
NULL. Text uses UTF-8 bytes after no implicit trimming or case folding. Numeric,
UUID and date canonicalization will be specified per type before implementation.

The first implementation scope is deliberately small and typed:

| PostgreSQL type family | Canonical form | Output form |
| --- | --- | --- |
| `text`, `varchar`, `citext` | UTF-8 bytes, unchanged | UTF-8 text with a fixed prefix and alphabet |
| `uuid` | 16-byte RFC 9562 value | UUID-shaped text; version/variant are documented as synthetic |
| `int2`, `int4`, `int8` | Signed big-endian two's-complement bytes | Decimal value in the target range; rejection on overflow |

Other types, domains over unsupported types, arrays and composite values are
rejected until their canonical forms and constraint behavior are reviewed.
Canonicalization is performed before worker fan-out and is independent of SQL
locale, connection encoding and worker count. A domain uses its base type only
when the resulting value is checked against the domain on restore.

## Key lifecycle

Keys are supplied through a protected file descriptor or operating-system secret
store, never as a CLI literal. File permissions and ownership are checked. The
key is held only for the process lifetime and is excluded from diagnostics.
Rotation is an explicit profile/version change; no automatic fallback is allowed.

The CLI interface will accept `--pseudonym-key-fd=FD` (an already-open readable
descriptor) and reject paths, values and environment-variable expansion. The
reader consumes exactly one bounded key record, clears its buffer on exit, and
refuses descriptors that are writable, seekable regular files with group/world
access, or longer than the configured maximum. Profiles contain only a key
identifier/domain; never key material. The descriptor is marked close-on-exec
and is not inherited by helper processes.

## Collisions and parallelism

The primitive output is encoded with a fixed, documented alphabet and length.
Truncation is rejected unless the caller opts into a documented collision risk.
Parallel workers share the immutable key and canonicalization rules, so the same
input produces the same pseudonym across formats and worker counts.

Before implementation, the test plan must prove that command-line listings,
process environments, generated SQL, dump comments/metadata, diagnostics,
attestations and child-process arguments contain neither key bytes nor a
recoverable encoding. Tests also compare serial and parallel output, separate
two keys and two domains, preserve NULL, exercise empty values and verify
typed/FK/unique constraints after restore. Collision tests use the full output
space; truncation is never silently introduced.

## Scope gate

Implementation may begin only after a reviewed primitive, supported-type table,
key input interface, and leakage tests are committed. Until then, existing
masking presets remain the supported privacy mechanism.
