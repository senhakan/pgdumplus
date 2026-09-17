# Security policy

## Supported versions

| Version | Security fixes |
| --- | --- |
| 1.2.x | Yes, compatible fixes only |
| 2.x (when released) | Yes |
| Older versions | No; upgrade to a supported release |

PostgreSQL 13 client packages are legacy compatibility artifacts. Keep the
client and server major versions aligned and apply PostgreSQL security updates
through the operating system or upstream project.

## Reporting a vulnerability

Please use GitHub's private security advisory workflow for this repository.
Do not open a public issue containing credentials, personal data, production
connection details, or an exploitable proof of concept. Include the affected
commit or release, package format, PostgreSQL major version, and a minimal
reproduction with sensitive values removed.

We will acknowledge reports as soon as practical, investigate privately, and
publish a fix or mitigation in a new release. Do not overwrite or move an
existing release tag.
