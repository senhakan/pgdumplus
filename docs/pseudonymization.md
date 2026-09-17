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

## Key lifecycle

Keys are supplied through a protected file descriptor or operating-system secret
store, never as a CLI literal. File permissions and ownership are checked. The
key is held only for the process lifetime and is excluded from diagnostics.
Rotation is an explicit profile/version change; no automatic fallback is allowed.

## Collisions and parallelism

The primitive output is encoded with a fixed, documented alphabet and length.
Truncation is rejected unless the caller opts into a documented collision risk.
Parallel workers share the immutable key and canonicalization rules, so the same
input produces the same pseudonym across formats and worker counts.

## Scope gate

Implementation may begin only after a reviewed primitive, supported-type table,
key input interface, and leakage tests are committed. Until then, existing
masking presets remain the supported privacy mechanism.
