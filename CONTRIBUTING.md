# Contributing to pg_dumpplus

Issues and pull requests are welcome. Please describe the PostgreSQL major
version, operating system, command-line options, and a minimal reproducible
example using synthetic data. Remove credentials, connection details, and
personal or production data before sharing logs or dumps.

Behavior changes need regression coverage in `scripts/verify_isolated.py` or an
equivalent disposable test. Run the checks relevant to your change:

```bash
git diff --check
python3 -m py_compile scripts/*.py
```

Changes to the generated client must be made through
`scripts/apply_pgdumpplus.py` and tested against a pristine supported
PostgreSQL source. Do not change an existing release tag or claim support for
an untested platform. See [PLAN.md](PLAN.md) for the support and release gates.

Security vulnerabilities must be reported privately as described in
[SECURITY.md](SECURITY.md), not in a public issue.
