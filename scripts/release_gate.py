#!/usr/bin/env python3
"""Block v2 publication until the release-boundary tasks are complete."""
import re
import sys
from pathlib import Path

REQUIRED = ("A1", "A2", "A3", "B1", "B2", "D3a")


def statuses(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*([^|]+?)\s*\|\s*(READY|IN_PROGRESS|BLOCKED|DONE)\s*\|", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def main(argv):
    tag = argv[1] if len(argv) > 1 else ""
    if not tag.startswith("v2"):
        return 0
    task_file = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent.parent / "TASKS.md"
    current = statuses(task_file)
    incomplete = [task for task in REQUIRED if current.get(task) != "DONE"]
    if incomplete:
        print("v2 release blocked; incomplete plan tasks: " + ", ".join(incomplete), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
