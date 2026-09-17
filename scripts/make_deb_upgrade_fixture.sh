#!/usr/bin/env bash
# Create a disposable lower-project-version DEB from an already-built package.
# The payload is unchanged; this is only for package-manager ordering tests.
set -euo pipefail
input=${1:?usage: make_deb_upgrade_fixture.sh PACKAGE OUTPUT}
output=${2:?usage: make_deb_upgrade_fixture.sh PACKAGE OUTPUT}
[[ -f "$input" && "$output" != "$input" ]]
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
dpkg-deb -R "$input" "$tmp/root"
control="$tmp/root/DEBIAN/control"
version=$(sed -n 's/^Version: //p' "$control")
[[ "$version" =~ ^[1-9][0-9]*\.[0-9]+\.[0-9]+- ]] || {
  echo "unexpected package version: $version" >&2
  exit 1
}
suffix=${version#*-}
sed -i "s/^Version: .*/Version: 1.1.0-1-$suffix/" "$control"
dpkg-deb --build --root-owner-group "$tmp/root" "$output" >/dev/null
dpkg-deb --field "$output" Version | grep -qx "1.1.0-1-$suffix"
