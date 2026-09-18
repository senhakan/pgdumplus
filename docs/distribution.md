# Package distribution contract

This document describes the channel contract for a future hosted APT/RPM
distribution. Standalone release downloads remain the supported distribution
method today; no repository endpoint or signing key is embedded in the client.

## Channels

`candidate` and `stable` are separate immutable channels. A package is promoted
by copying the exact already-verified bytes; it is never rebuilt during
promotion. Standalone archives and checksums remain available after promotion.

Repository metadata is signed with a dedicated offline-controlled key. The
public key is distributed out of band and rotated by publishing a new key,
overlapping trust during the transition, and documenting its retirement. A
revoked or expired key must fail closed. Private keys never enter CI logs,
profiles, packages, container images or repository contents.

## Client-side verification

Before installation, operators should verify the package-manager metadata and
the package signature using the vendor key, then install from the selected
channel. A clean host must be tested for fresh installation, upgrade from the
previous release, downgrade guidance, signature rejection and removal. Runtime
containers used for these checks must not contain compilers or build tools.

The repository service, DNS, signing-key owner and retention policy are release
decisions outside this source tree. Until those decisions and independent
channel tests exist, documentation must point users to the signed standalone
release assets and their checksums rather than an unprovisioned repository.
