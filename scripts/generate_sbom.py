#!/usr/bin/env python3
"""Generate a deterministic SPDX 2.3 inventory for release files."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "all-dist")
    files = sorted(p for p in root.iterdir()
                   if p.is_file() and p.name != "SBOM.spdx.json")
    entries = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({
            "SPDXID": "SPDXRef-" + path.name.replace(".", "-"),
            "name": path.name,
            "downloadLocation": "NOASSERTION",
            "checksums": [{"algorithm": "SHA256", "checksumValue": digest}],
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
        })
    doc = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "pg_dumpplus-release-assets",
        "documentNamespace": "https://github.com/senhakan/pgdumpplus/sbom",
        "creationInfo": {"creators": ["Tool: pg_dumpplus-build"], "created": "1970-01-01T00:00:00Z"},
        "packages": entries,
    }
    print(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
