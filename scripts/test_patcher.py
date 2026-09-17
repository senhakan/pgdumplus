#!/usr/bin/env python3
"""Check patch application on a pristine upstream source tree (no database)."""
import argparse
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    patcher = Path(__file__).with_name("apply_pgdumpplus.py")
    spec = importlib.util.spec_from_file_location("patcher", patcher)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="pgdp_patch_test_") as temp:
        root = Path(temp)

        def fresh(name):
            target = root / name
            for rel in module.PATCH_FILES:
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(args.source / rel, dest)
            return target

        def snapshot(tree):
            return {str(p.relative_to(tree)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in tree.rglob("*") if p.is_file()}

        def run(tree, success):
            result = subprocess.run([sys.executable, str(patcher), str(tree)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            if (result.returncode == 0) != success:
                raise AssertionError(result.stdout + result.stderr)

        clean = fresh("clean")
        run(clean, True)
        assert (clean / ".pgdumpplus-patch.json").exists()
        before = snapshot(clean)
        run(clean, True)
        assert before == snapshot(clean), "second application changed files"
        print("PASS clean application and verified idempotence")

        broken = fresh("anchor_failure")
        makefile = broken / "src/bin/pg_dump/Makefile"
        makefile.write_text(makefile.read_text().replace("pg_dump:", "broken_target:"))
        before = snapshot(broken)
        run(broken, False)
        assert before == snapshot(broken), "anchor failure modified the source tree"
        print("PASS late anchor failure leaves every file unchanged")

        old = fresh("old_patch")
        source = old / "src/bin/pg_dump/pg_dump.c"
        source.write_text(source.read_text() + "\n/* pg_dumpplus old patch */\n")
        before = snapshot(old)
        run(old, False)
        assert before == snapshot(old)
        print("PASS old/partial patch rejected without writes")

        source = clean / "src/bin/pg_dump/pg_dump.c"
        source.write_text(source.read_text() + "\n/* external edit */\n")
        before = snapshot(clean)
        run(clean, False)
        assert before == snapshot(clean)
        print("PASS modified patched source rejected without writes")

        revision = fresh("revision")
        run(revision, True)
        manifest = revision / ".pgdumpplus-patch.json"
        import json
        state = json.loads(manifest.read_text())
        state["patcher"] = "obsolete"
        manifest.write_text(json.dumps(state))
        before = snapshot(revision)
        run(revision, False)
        assert before == snapshot(revision)
        print("PASS different patch revision requires clean source")


if __name__ == "__main__":
    main()
