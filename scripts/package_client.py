#!/usr/bin/env python3
"""Build native client-only packages without installing into the build host.

Build dependencies must already be installed. Each invocation owns a fresh
workspace; existing source trees, installed packages and system configuration
are never modified. Workspaces and logs are retained for inspection.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from apply_pgdumpplus import PATCH_FILES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def supported_majors():
    with open(ROOT / "support-matrix.json", encoding="utf-8") as stream:
        data = json.load(stream)
    return {str(item["major"]) for item in data["postgresql"]}


def source_hash(version):
    with open(ROOT / "support-matrix.json", encoding="utf-8") as stream:
        data = json.load(stream)
    for item in data["postgresql"]:
        if item.get("tested_minor") == version:
            return item.get("source_sha256")
    return None


def project_version():
    with open(ROOT / "support-matrix.json", encoding="utf-8") as stream:
        value = json.load(stream).get("project_version")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise RuntimeError("support-matrix.json has an invalid project_version")
    return value


def run(argv, cwd=None, env=None, log=None):
    print("+ " + " ".join(str(v) for v in argv), flush=True)
    if log:
        with open(log, "w") as stream:
            result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env,
                                    stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print(Path(log).read_text()[-6000:], file=sys.stderr)
            raise RuntimeError("command failed; see " + str(log))
        return ""
    return subprocess.check_output([str(v) for v in argv], cwd=cwd, env=env, universal_newlines=True)


def os_label():
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"')
    ident, version = values["ID"], values["VERSION_ID"]
    if ident in ("rhel", "rocky", "almalinux", "centos", "ol"):
        return "el" + version.split(".")[0]
    return ident + version


def archive(root, output):
    with tarfile.open(str(output), "w:gz", dereference=False) as tar:
        for name in ("opt", "usr"):
            tar.add(str(root / name), arcname=name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="PostgreSQL version, e.g. 18.6")
    parser.add_argument("--format", choices=("rpm", "deb"), required=True)
    parser.add_argument("--build-dir", type=Path, default=Path("_build"))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--source-archive", type=Path, help="existing upstream source tarball")
    parser.add_argument("--revision", default="2", help="positive native package revision")
    args = parser.parse_args()
    majors = supported_majors()
    if not re.fullmatch(r"(?:" + "|".join(sorted(majors)) + r")\.[0-9]+", args.version):
        parser.error("source version is not listed in support-matrix.json")
    if not re.fullmatch(r"[1-9][0-9]*", args.revision):
        parser.error("revision must be a positive integer")
    major = args.version.split(".")[0]
    project = project_version()
    label = os_label()
    if not re.fullmatch(r"[a-z0-9.]+", label):
        parser.error("unsupported OS label")
    arch = platform.machine()
    if arch != "x86_64":
        parser.error("currently verified package architecture is x86_64")
    args.build_dir.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve()
    work = Path(tempfile.mkdtemp(prefix="pgdp-", dir=str(args.build_dir.resolve())))
    print("Workspace: " + str(work), flush=True)
    tag = "REL_" + args.version.replace(".", "_")
    source_archive = args.source_archive.resolve() if args.source_archive else work / "upstream.tar.gz"
    if not args.source_archive:
        run(["curl", "-fsSL", "--retry", "3", "--connect-timeout", "15",
             "--max-time", "300", "-o", source_archive,
             "https://codeload.github.com/postgres/postgres/tar.gz/refs/tags/" + tag])
    expected_hash = source_hash(args.version)
    if expected_hash:
        actual_hash = hashlib.sha256(source_archive.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise RuntimeError("upstream source hash does not match support-matrix.json")
    # Only regular files and directories from the expected upstream root are allowed.
    source = work / ("postgres-" + tag)
    with tarfile.open(str(source_archive)) as tar:
        for member in tar.getmembers():
            path = Path(member.name)
            if (path.is_absolute() or ".." in path.parts or
                    path.parts[0] != source.name or not (member.isfile() or member.isdir())):
                raise RuntimeError("unexpected source archive member: " + member.name)
        tar.extractall(str(work))
    original = {name: (source / name).read_bytes() for name in PATCH_FILES}
    print(run([sys.executable, HERE / "test_patcher.py", source]), end="")
    print(run([sys.executable, HERE / "apply_pgdumpplus.py", source]), end="")
    prefix = "/opt/pgdumpplus/" + major
    env = dict(os.environ)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=str(HERE.parent), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    cppflags = env.get("CPPFLAGS", "")
    env["CPPFLAGS"] = (cppflags + " -DPGDUMPPLUS_PROJECT_VERSION=\\\"" + project
                        + "\\\" -DPGDUMPPLUS_SOURCE_COMMIT=\\\"" + commit + "\\\"").strip()
    # Make reduces $$ to $, then the shell quotes preserve the literal ELF token.
    env["LDFLAGS"] = "-Wl,-rpath,'$$ORIGIN/../lib',--enable-new-dtags"
    run(["./configure", "--prefix=" + prefix, "--without-readline", "--without-icu",
         "--with-openssl", "--disable-rpath"], source, env, work / "configure.log")
    run(["make", "-C", "src/backend", "generated-headers"], source, env, work / "headers.log")
    run(["make", "-C", "src/bin/pg_dump", "-j1"], source, env, work / "build.log")
    staging = work / "install"
    for directory in ("src/interfaces/libpq", "src/bin/pg_dump"):
        run(["make", "-C", directory, "install", "DESTDIR=" + str(staging)],
            source, env, work / (directory.split("/")[-1] + "-install.log"))
    installed = staging / prefix.lstrip("/")
    root = work / "payload"
    client = root / prefix.lstrip("/")
    (client / "bin").mkdir(parents=True)
    (client / "lib").mkdir()
    (client / "share/licenses").mkdir(parents=True)
    for name in ("pg_dumpplus", "pg_restore"):
        shutil.copy2(installed / "bin" / name, client / "bin" / name)
    for path in (installed / "lib").glob("libpq.so.*"):
        shutil.copy2(path, client / "lib" / path.name, follow_symlinks=False)
    if not (client / "lib/libpq.so.5").exists():
        raise RuntimeError("staged libpq is missing")
    shutil.copy2(HERE.parent / "LICENSE", client / "share/licenses/pgdumpplus-LICENSE")
    shutil.copy2(source / "COPYRIGHT", client / "share/licenses/PostgreSQL-COPYRIGHT")
    commands = root / "usr/bin"
    commands.mkdir(parents=True)
    aliases = {"pg_dumpplus-" + major: "pg_dumpplus", "pg_restoreplus-" + major: "pg_restore"}
    if major == "18":
        aliases["pg_dumpplus"] = "pg_dumpplus"
    for name, target in aliases.items():
        (commands / name).symlink_to("../../opt/pgdumpplus/" + major + "/bin/" + target)
    for name in ("pg_dumpplus", "pg_restore"):
        binary = client / "bin" / name
        dynamic = run(["readelf", "-d", binary])
        if "$ORIGIN/../lib" not in dynamic or "$$ORIGIN" in dynamic:
            raise RuntimeError("incorrect runtime library search path")
        linked = run(["ldd", binary])
        if "not found" in linked or str(client / "lib") not in linked:
            # ldd may preserve bin/../lib instead of canonicalizing it.
            if "not found" in linked or str(client / "bin/../lib") not in linked:
                raise RuntimeError("private libpq was not loaded: " + linked)
        print(run([binary, "--version"]).strip())
    # Platform-specific names avoid artifact merge collisions. Only source diffs.
    patch = output / ("pgdumpplus-" + args.version + "-" + label + ".patch")
    with patch.open("w") as stream:
        for name in PATCH_FILES:
            old = work / "original" / name
            old.parent.mkdir(parents=True, exist_ok=True)
            old.write_bytes(original[name])
            result = subprocess.run(["diff", "-u", "--label", "a/" + name,
                                     "--label", "b/" + name, str(old), str(source / name)],
                                    stdout=stream)
            if result.returncode not in (0, 1):
                raise RuntimeError("source diff failed")
    tarball = output / ("pgdumpplus-{}-{}-{}-linux-{}.tar.gz".format(major, args.version, label, arch))
    archive(root, tarball)
    if args.format == "rpm":
        top = work / "rpmbuild"
        for directory in ("SOURCES", "SPECS", "BUILD", "RPMS", "SRPMS"):
            (top / directory).mkdir(parents=True)
        shutil.copy2(tarball, top / "SOURCES" / tarball.name)
        spec = top / "SPECS/pgdumpplus.spec"
        release = args.revision + "." + label
        spec.write_text("""%global debug_package %{nil}
%global _build_id_links none
%global __provides_exclude ^libpq\\.so.*$
%global __requires_exclude ^libpq\\.so.*$
Name: pgdumpplus-@MAJOR@
Version: @VERSION@
Release: @RELEASE@
Summary: pg_dumpplus @PROJECT@ PostgreSQL @UPSTREAM@ dump client
License: PostgreSQL
URL: https://github.com/senhakan/pgdumpplus
Source0: @TARBALL@

%description
Precompiled pg_dumpplus @PROJECT@ client built from PostgreSQL @UPSTREAM@.
No server or compiler is installed. Includes a private libpq; system
PostgreSQL tools are unchanged.

%prep
%setup -q -c -T -a0

%install
mkdir -p %{buildroot}
cp -a opt usr %{buildroot}/

%files
/opt/pgdumpplus/@MAJOR@
@COMMANDS@
        """.replace("@MAJOR@", major).replace("@VERSION@", project)
                        .replace("@PROJECT@", project).replace("@UPSTREAM@", args.version)
                        .replace("@RELEASE@", release).replace("@TARBALL@", tarball.name)
                        .replace("@COMMANDS@", "\n".join("/usr/bin/" + n for n in aliases)))
        run(["rpmbuild", "--define", "_topdir " + str(top), "-bb", spec], log=work / "rpm.log")
        rpms = list((top / "RPMS").rglob("*.rpm"))
        if len(rpms) != 1:
            raise RuntimeError("expected one client RPM")
        package = output / rpms[0].name
        shutil.copy2(rpms[0], package)
    else:
        package_name = "pgdumpplus-" + major
        native_arch = run(["dpkg", "--print-architecture"]).strip()
        suffix = {"ubuntu22.04": "u2204", "ubuntu24.04": "u2404", "debian12": "d12"}.get(label, label.replace(".", ""))
        version = project + "-" + args.revision + suffix
        (work / "debian").mkdir()
        (work / "debian/control").write_text(
            "Source: " + package_name + "\nSection: database\nPriority: optional\n"
            "Maintainer: senhakan <senhakan@users.noreply.github.com>\n\n"
            "Package: " + package_name + "\nArchitecture: any\nDescription: PostgreSQL dump client\n")
        (work / "debian/shlibs.local").write_text("libpq 5 " + package_name + " (= " + version + ")\n")
        (root / "DEBIAN").mkdir()
        elf_files = list((client / "bin").iterdir()) + [p for p in (client / "lib").iterdir() if not p.is_symlink()]
        dependencies = run(["dpkg-shlibdeps", "-O", "-x" + package_name,
                            "-l" + str(client / "lib"), *["-e" + str(p) for p in elf_files]], cwd=work)
        depends = next(line.split("=", 1)[1] for line in dependencies.splitlines() if line.startswith("shlibs:Depends="))
        (root / "DEBIAN/control").write_text(
            "Package: " + package_name + "\nVersion: " + version + "\nArchitecture: " + native_arch +
            "\nSection: database\nPriority: optional\nDepends: " + depends +
            "\nMaintainer: senhakan <senhakan@users.noreply.github.com>\n"
            "Description: pg_dumpplus " + project + " PostgreSQL " + args.version + " dump client\n"
            " Precompiled pg_dumpplus matching restore client and private libpq.\n"
            " No server or compiler is installed. System PostgreSQL tools are unchanged.\n")
        package = output / (package_name + "_" + version + "_" + native_arch + ".deb")
        run(["dpkg-deb", "--build", "--root-owner-group", root, package])
    manifest = work / "artifacts.sha256"
    manifest.write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n"
                                for p in (package, tarball, patch)))
    print("Package: " + str(package))
    print("Payload: " + str(root))
    print("Checksums: " + str(manifest))


if __name__ == "__main__":
    main()
