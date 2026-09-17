#!/usr/bin/env python3
"""Verify a dump client using small, disposable, uniquely named databases.

Requires Python 3 and PostgreSQL client tools. Connection settings come from
PGHOST/PGPORT/PGUSER/PGPASSWORD/PGPASSFILE. Run as a role with CREATEDB.
Only databases successfully created by this invocation are removed. No FORCE
drop, existing database reuse, or access to application tables is performed.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid


FIXTURE = """
CREATE TABLE customers (
    id integer PRIMARY KEY, full_name text, ssn varchar(11), phone text,
    address text, birth_year integer,
    doubled integer GENERATED ALWAYS AS (id * 2) STORED
);
INSERT INTO customers (id, full_name, ssn, phone, address, birth_year)
SELECT g, 'Customer ' || g, '12345678901', '05551234567',
       'Address ' || g, 1980 + g % 30
FROM generate_series(1,100) g;
CREATE TABLE orders (
    id integer PRIMARY KEY, customer_id integer REFERENCES customers(id),
    payload text NOT NULL
);
INSERT INTO orders SELECT g, (g - 1) % 100 + 1, 'payload-' || g
FROM generate_series(1,1000) g;
CREATE TABLE "Odd:Table" (id integer PRIMARY KEY, "Secret:Value" text,
    "A""B" text, "select" text);
INSERT INTO "Odd:Table" VALUES
    (1, 'private-value', 'quoted', 'keyword'),
    (2, 'another-value', 'quoted', 'keyword');
CREATE TABLE mask_edges (id integer PRIMARY KEY, value text);
INSERT INTO mask_edges VALUES
    (1, NULL), (2, ''), (3, '1'), (4, '12'), (5, '123'), (6, '1234'), (7, '12345');
"""


class Suite:
    def __init__(self, args, work):
        self.args = args
        self.work = Path(work)
        self.env = dict(os.environ, PGCONNECT_TIMEOUT="10")
        suffix = uuid.uuid4().hex[:16]
        self.source = "pgdp_verify_" + suffix + "_src"
        self.target = "pgdp_verify_" + suffix + "_dst"
        self.created = []
        self.results = []
        self.serial = 0

    def run(self, argv, check=True):
        result = subprocess.run(
            [str(v) for v in argv], env=self.env, universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        )
        if check and result.returncode:
            raise RuntimeError("{} exited {}: {}".format(
                Path(str(argv[0])).name, result.returncode, result.stderr.strip()))
        return result

    def sql(self, database, query):
        return self.run([
            self.args.psql, "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
            "-d", database, "-c", query,
        ]).stdout.strip()

    def setup(self):
        for database in (self.source, self.target):
            self.sql(self.args.maintenance_db, 'CREATE DATABASE "{}" TEMPLATE template0'.format(database))
            self.created.append(database)
        self.sql(self.source, FIXTURE)

    def cleanup(self):
        errors = []
        for database in reversed(self.created):
            try:
                self.sql(self.args.maintenance_db, 'DROP DATABASE "{}"'.format(database))
            except Exception as exc:
                errors.append("{}: {}".format(database, exc))
        if errors:
            raise RuntimeError("Cleanup failed; remove only these test databases: " + "; ".join(errors))

    def dump(self, options=(), fmt="c", binary=None, check=True):
        self.serial += 1
        path = self.work / ("dump_" + str(self.serial))
        result = self.run([
            binary or self.args.binary, "-d", self.source, "--no-owner",
            "--no-privileges", "--lock-wait-timeout=10s", "-F", fmt,
            *options, "-f", path,
        ], check=check)
        return path, result

    def restore(self, path, fmt="c"):
        # self.target was created successfully by this run, never supplied by a user.
        self.sql(self.target, "DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        if fmt == "p":
            self.run([self.args.psql, "-X", "-q", "-v", "ON_ERROR_STOP=1",
                      "-d", self.target, "-f", path])
        else:
            self.run([self.args.pg_restore, "--exit-on-error", "--no-owner",
                      "--no-privileges", "-d", self.target, path])

    @staticmethod
    def equal(actual, expected):
        if actual != expected:
            raise AssertionError("expected {!r}, got {!r}".format(expected, actual))

    def case(self, name, action):
        try:
            action()
        except Exception as exc:
            self.results.append({"name": name, "passed": False, "detail": str(exc)})
            print("FAIL {}: {}".format(name, exc), flush=True)
        else:
            self.results.append({"name": name, "passed": True})
            print("PASS " + name, flush=True)

    def roundtrip(self, options, query, expected, fmt="c"):
        path, _ = self.dump(options, fmt)
        self.restore(path, fmt)
        self.equal(self.sql(self.target, query), expected)

    def error(self, option, fragment):
        _, result = self.dump([option], check=False)
        if result.returncode == 0 or fragment not in result.stderr:
            raise AssertionError("expected failure containing {!r}; exit={}, stderr={}".format(
                fragment, result.returncode, result.stderr.strip()))

    def unfiltered(self):
        normal, _ = self.dump(fmt="p", binary=self.args.vanilla)
        plus, _ = self.dump(fmt="p")
        # Recent PostgreSQL clients use a different random psql guard per dump.
        def normalize(path):
            return re.sub(r"^\\(?:un)?restrict .*$", "", path.read_text(), flags=re.M)
        self.equal(normalize(plus), normalize(normal))
        self.restore(plus, "p")
        self.equal(self.sql(self.target, "SELECT count(*) FROM orders"), "1000")

    def skipped_mask(self):
        path, result = self.dump(["--mask=public.customers:missing_column:all"])
        if "not found in table" not in result.stderr:
            raise AssertionError("missing-column warning absent")
        self.restore(path)
        self.equal(self.sql(self.target, "SELECT ssn FROM customers WHERE id=1"), "12345678901")

    def checks(self):
        self.case("unfiltered dump matches upstream (random guards normalized)", self.unfiltered)
        for fmt, extra in (("c", []), ("p", []), ("p", ["--inserts"]),
                           ("p", ["--column-inserts"]), ("d", ["-j", "2"])):
            label = fmt + (" " + " ".join(extra) if extra else "")
            self.case("filter + multi-mask roundtrip " + label, lambda fmt=fmt, extra=extra:
                self.roundtrip([
                    "--where=public.orders:id <= 25",
                    "--mask=public.customers:ssn:tc",
                    "--mask=public.customers:phone:phone",
                    "--mask=public.customers:full_name:all", *extra,
                ], "SELECT (SELECT count(*) FROM orders), (SELECT count(*) FROM customers), "
                   "ssn, phone, full_name, doubled FROM customers WHERE id=1",
                   "25|100|12*******01|********567|**********|2", fmt))
        self.case("FK-consistent parent and child filters", lambda: self.roundtrip([
            "--where=public.customers:id <= 10", "--where=public.orders:customer_id <= 10",
        ], "SELECT (SELECT count(*) FROM customers), count(*), "
           "count(*) FILTER (WHERE c.id IS NULL) FROM orders o LEFT JOIN customers c ON c.id=o.customer_id",
           "10|100|0"))
        self.case("wildcard filter", lambda: self.roundtrip([
            "--where=public.ord*:id <= 12",
        ], "SELECT count(*) FROM orders", "12"))
        self.case("quoted table and column filter", lambda: self.roundtrip([
            '--where=public."Odd:Table":"Secret:Value" = \'private-value\'',
        ], 'SELECT count(*) FROM "Odd:Table"', "1"))
        self.case("table selection and filter", lambda: self.roundtrip([
            "-t", "public.customers", "--where=public.customers:id <= 3",
        ], "SELECT count(*) FROM customers", "3"))
        self.case("custom text and integer masks", lambda: self.roundtrip([
            "--mask=public.customers:full_name:upper(full_name)",
            "--mask=public.customers:birth_year:2000",
        ], "SELECT full_name, birth_year FROM customers WHERE id=2", "CUSTOMER 2|2000"))
        self.case("missing mask column warns and retains raw data (current behavior)", self.skipped_mask)
        for name, option, fragment in (
            ("where separator", "--where=public.orders", "missing"),
            ("where table", "--where=public.no_such_table:id=1", "no matching"),
            ("where SQL", "--where=public.orders:no_such_column=1", "does not exist"),
            ("mask separator", "--mask=public.customers:ssn", "missing"),
            ("mask table", "--mask=public.no_such_table:ssn:all", "no matching"),
            ("mask SQL", "--mask=public.customers:ssn:no_such_function(ssn)", "does not exist"),
            ("qualified mask column", "--mask=public.customers:customers.ssn:all", "single SQL identifier"),
        ):
            self.case("error: " + name, lambda option=option, fragment=fragment: self.error(option, fragment))
        self.case("quoted mask column", lambda: self.roundtrip([
            '--mask=public."Odd:Table":"Secret:Value":all',
        ], 'SELECT "Secret:Value" FROM "Odd:Table" WHERE id=1', "*************"))
        self.case("escaped identifier and keyword masks with column inserts", lambda: self.roundtrip([
            '--mask=public."Odd:Table":"A""B":all',
            '--mask=public."Odd:Table":"select":all', "--column-inserts",
        ], 'SELECT "A""B", "select" FROM "Odd:Table" WHERE id=1', "******|*******", "p"))
        self.case("unquoted mask identifier folds case", lambda: self.roundtrip([
            "--mask=public.customers:FULL_NAME:all",
        ], "SELECT full_name FROM customers WHERE id=1", "**********"))
        self.case("all preset preserves NULL", lambda: self.roundtrip([
            "--mask=public.mask_edges:value:all",
        ], "SELECT value IS NULL FROM mask_edges WHERE id=1", "t"))
        self.case("tc preset preserves short-value length", lambda: self.roundtrip([
            "--mask=public.mask_edges:value:tc",
        ], "SELECT string_agg(length(value)::text, ',' ORDER BY id) FROM mask_edges WHERE id >= 2",
           "0,1,2,3,4,5"))
        self.case("tc preset masks all characters in short values", lambda: self.roundtrip([
            "--mask=public.mask_edges:value:tc",
        ], "SELECT string_agg(value, ',' ORDER BY id) FROM mask_edges WHERE id >= 2",
           ",*,**,***,****,12*45"))
        self.case("all preset preserves empty string", lambda: self.roundtrip([
            "--mask=public.mask_edges:value:all",
        ], "SELECT length(value) FROM mask_edges WHERE id=2", "0"))
        for preset in ("tc", "phone"):
            self.case(preset + " preset preserves NULL", lambda preset=preset: self.roundtrip([
                "--mask=public.mask_edges:value:" + preset,
            ], "SELECT value IS NULL FROM mask_edges WHERE id=1", "t"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, help="pg_dumpplus executable")
    parser.add_argument("--vanilla", required=True, help="matching upstream pg_dump executable")
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--pg-restore", default="pg_restore")
    parser.add_argument("--maintenance-db", default="postgres")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pgdp_verify_") as work:
        suite = Suite(args, work)
        try:
            suite.setup()
            suite.checks()
        finally:
            suite.cleanup()
        failed = sum(not r["passed"] for r in suite.results)
        print(json.dumps({"passed": len(suite.results) - failed, "failed": failed,
                          "results": suite.results}, ensure_ascii=False))
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
