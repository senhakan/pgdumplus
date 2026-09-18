# Changelog

## 2.0.0

- Added compiled `--profile=FILE` support for strict profile v1 JSON files;
  profiles merge with CLI filters/masks and are validated before export.

## 2.0.0-rc.1 (previous candidate)

- Invalid masking rules now fail before table data export instead of being
  silently skipped.
- Added catalog-only `--dry-run` plans in text and JSON (`schema_version: 1`).
- Added deterministic SPDX release SBOM generation and consolidated support
  metadata.
- Current candidate builds target PostgreSQL 13.23 (legacy), 17.11 and 18.6;
  package metadata separates the project version from the upstream PostgreSQL
  version.
- Release assets are checksummed and accompanied by GitHub provenance
  attestations.

Migration: review existing `--mask` rules before upgrading. Missing columns,
generated or dropped columns, excluded tables, duplicate rules, and text
presets on non-text columns now return an error. Discard any partial output
after a failed command and correct the rule before retrying.

## 1.2.0

- Initial public package channel with PostgreSQL 13 and 17 client builds.
