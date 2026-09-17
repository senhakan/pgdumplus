#!/usr/bin/env bash
# Build a DEB and tarball. Dependencies are installed by the build environment.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/package_client.py" "${PGVER:?set PGVER, e.g. 18.6}" \
  --format deb --build-dir "${BUILD_DIR:-$PWD/_build}" --output "${1:-$PWD/dist}"
