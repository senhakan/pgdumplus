# Changelog

## Unreleased (v2.0.0 candidate)

- Invalid masking rules now fail before table data export instead of being
  silently skipped.
- Added catalog-only `--dry-run` plans in text and JSON (`schema_version: 1`).
- Added deterministic SPDX release SBOM generation and consolidated support
  metadata.

Migration: review existing `--mask` rules before upgrading. Missing columns,
generated or dropped columns, excluded tables, duplicate rules, and text
presets on non-text columns now return an error. Discard any partial output
after a failed command and correct the rule before retrying.

## 1.2.0

- Initial public package channel with PostgreSQL 13 and 17 client builds.
