# pg_dumpplus launch draft

## Short announcement

pg_dumpplus is a compiled PostgreSQL dump client for focused exports and
explicit column masking. It keeps PostgreSQL's dump formats and snapshot
behavior while adding row filters, strict mask validation, catalog-only plans,
and packages that install without a compiler or Python runtime.

The `v2.0.0-rc.1` prerelease supports PostgreSQL 13.23 (legacy), 17.11 and
18.6 on the documented Linux x86_64 targets. Downloaded assets include checksums,
an SPDX SBOM and provenance attestations. See the release notes and support
matrix before testing.

pg_dumpplus is not an anonymization guarantee, hosted service or automatic PII
discovery tool. Use synthetic or approved data and review restore constraints.

## Community post checklist

- Link to the repository and the candidate release.
- Mention the supported PostgreSQL/OS matrix and the legacy status of PG13.
- Include one tenant-filter and one masked-extract example from `docs/tutorials.md`.
- Link to checksum, SBOM and provenance verification instructions.
- Invite redacted bug reports with the issue templates; do not request private data.
- Publish manually only after reviewing the candidate assets and project policy.

