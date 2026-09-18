# Pseudonymization security review checklist

This checklist is an implementation gate for the design in
[`pseudonymization.md`](pseudonymization.md). It is not an approval of a
released feature. The feature remains unavailable until every blocking item has
independent evidence.

## Decisions to preserve

| Boundary | Required decision | Evidence before implementation |
| --- | --- | --- |
| Primitive | HMAC-SHA-256 with a domain-separated message; plain hashes are not acceptable | Frontend API review and known-answer tests |
| Key input | One bounded record from an already-open read-only FD; no path, literal or environment fallback | Linux/macOS descriptor tests and process/argument inspection |
| Execution | Canonicalize and derive locally; the key never enters SQL, connection parameters, dump metadata or child arguments | SQL capture, metadata scan and child-process test |
| Text | UTF-8 bytes, unchanged; no implicit trim, case fold or locale conversion | Unicode/invalid-encoding fixtures |
| UUID | 16-byte RFC 9562 value; synthetic version/variant documented | Typed roundtrip and known-answer vectors |
| Integers | Signed big-endian two's-complement bytes; reject output overflow | int2/int4/int8 boundary fixtures |
| Collision | Fixed output space, no silent truncation; uniqueness/FK constraints checked after restore | Full-width vectors and constraint roundtrips |
| Parallelism | Immutable key and canonicalization shared by workers; serial and parallel bytes agree | Plain/custom/directory comparison |

## Leakage review gates

Before a release candidate can include this feature, tests must prove that key
bytes and recoverable encodings are absent from `ps`, `/proc`, environment
variables, generated SQL, dump comments, diagnostics, logs, attestations and
helper arguments. A failing or unavailable leakage test blocks the feature; it
does not downgrade to a weaker mask or unsalted hash.

## Current status

The design and this checklist are committed, but the primitive API review,
independent security review and runtime leakage/typed roundtrip evidence are
not complete. Therefore C2 remains blocked and no pseudonymization CLI option
is advertised or accepted by the release binaries.

