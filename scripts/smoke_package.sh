#!/usr/bin/env bash
# Run ONLY in a disposable runtime container: install, upgrade, verify, remove.
# Usage: smoke_package.sh <rpm|deb> <major> <package> [upgrade-package]
set -euo pipefail
FORMAT=${1:?}
MAJOR=${2:?}
OLDER=${3:?}
NEWER=${4:-}
[[ -f /.dockerenv || -f /run/.containerenv ]] || { echo 'Disposable container required' >&2; exit 1; }
[[ "$MAJOR" == 13 || "$MAJOR" == 17 || "$MAJOR" == 18 ]] || exit 1
if command -v gcc || command -v make; then
  echo 'Use a clean runtime image without build tools' >&2
  exit 1
fi
[[ ! -e /opt/pgdumpplus/$MAJOR ]]
[[ ! -e /usr/bin/pg_dump ]]

install_package() {
  if [[ "$FORMAT" == rpm ]]; then
    dnf install -y "$1"
  elif [[ "$FORMAT" == deb ]]; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$1"
  else
    exit 1
  fi
}
version() {
  if [[ "$FORMAT" == rpm ]]; then
    rpm -q --qf '%{VERSION}-%{RELEASE}' "pgdumpplus-$MAJOR"
  else
    dpkg-query -W -f='${Version}' "pgdumpplus-$MAJOR"
  fi
}
verify() {
  "pg_dumpplus-$MAJOR" --version
  info=$("pg_dumpplus-$MAJOR" --build-info)
  [[ "$info" == pg_dumpplus\ project\ *\;\ PostgreSQL\ *\;\ source\ * ]]
  if [[ -n "${EXPECTED_PROJECT_VERSION:-}" ]]; then
    [[ "$info" == *"project ${EXPECTED_PROJECT_VERSION};"* ]]
  fi
  "pg_restoreplus-$MAJOR" --version
  "pg_dumpplus-$MAJOR" --help | grep -- --mask
  "pg_dumpplus-$MAJOR" --help | grep -- --where
  [[ ! -e /opt/pgdumpplus/$MAJOR/bin/postgres ]]
  [[ ! -e /usr/bin/pg_dump ]]
  [[ -f /opt/pgdumpplus/$MAJOR/share/licenses/pgdumpplus-LICENSE ]]
  ldd "/opt/pgdumpplus/$MAJOR/bin/pg_dumpplus"
  if ldd "/opt/pgdumpplus/$MAJOR/bin/pg_dumpplus" | grep 'not found'; then exit 1; fi
  if command -v gcc || command -v make; then exit 1; fi
  if [[ "$MAJOR" == 18 ]]; then pg_dumpplus --version; fi
}
install_package "$OLDER"
BEFORE=$(version)
verify
if [[ -n "$NEWER" ]]; then
  install_package "$NEWER"
  AFTER=$(version)
  [[ "$BEFORE" != "$AFTER" ]]
  verify
  echo "PASS upgrade $BEFORE -> $AFTER"
fi
if [[ "$FORMAT" == rpm ]]; then
  rpm -e "pgdumpplus-$MAJOR"
else
  DEBIAN_FRONTEND=noninteractive apt-get purge -y "pgdumpplus-$MAJOR"
fi
[[ ! -e /opt/pgdumpplus/$MAJOR ]]
[[ ! -L /usr/bin/pg_dumpplus-$MAJOR ]]
[[ ! -L /usr/bin/pg_restoreplus-$MAJOR ]]
if [[ "$MAJOR" == 18 ]]; then [[ ! -L /usr/bin/pg_dumpplus ]]; fi
echo "PASS install, run and remove; no compiler required"
