#!/usr/bin/env bash
# Build an RPM and tarball. Dependencies are installed by the build environment.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
exec python3 "$HERE/package_client.py" "${1:?usage: build.sh PG_VERSION [BUILD_DIR]}" \
  --format rpm --build-dir "${2:-$PWD/_build}" --output "$PWD/dist"
