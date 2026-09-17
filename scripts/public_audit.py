#!/usr/bin/env python3
"""Fail if tracked files contain credentials or private infrastructure markers."""
import re
import subprocess
import sys

PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?:postgres(?:ql)?|mysql|redis)://[^\s:@]+:[^\s@]+@", re.I),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"\b(?:10\.(?:[0-9]{1,3}\.){2}[0-9]{1,3}|192\.168\.(?:[0-9]{1,3}\.)[0-9]{1,3})\b"),
)


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    findings = []
    for raw in names:
        if not raw:
            continue
        path = raw.decode("utf-8")
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        text = data.decode("utf-8", "replace")
        for number, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{path}:{number}")
    if findings:
        print("public audit failed: " + ", ".join(findings), file=sys.stderr)
        return 1
    print("public audit passed: no credential or private-network markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
