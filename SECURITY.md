# Security policy

## Supported version

Security fixes are applied to the latest commit on `main`. No released v2 line
exists yet. The feeder sidecar is research and operator-assistance software; it is
not certified avionics, an air-traffic-control system, or a source of separation
assurance.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or exposed credential.
Use GitHub's private vulnerability reporting for this repository. Include the
affected revision, impact, reproduction steps, and any proposed mitigation. Do not
include real receiver locations, raw RF captures, aircraft identifiers, or active
credentials. Maintainers should acknowledge a report within seven days and provide
status updates until remediation or documented closure.

## Security boundaries

- ADS-B input is untrusted and strictly parsed, bounded, and treated as evidence—not
  verified truth or proof of intent.
- The sidecar binds its host port to loopback by default, exposes read-only APIs,
  runs as UID/GID 10001, drops Linux capabilities, and uses a read-only root
  filesystem with a dedicated event volume.
- Production authentication requires an explicit secret; mutations require roles,
  a valid session, and an allowed Origin.
- CI blocks on dependency, secret, repository/configuration, and image critical
  findings. Release promotion additionally requires human review.

## Temporary dependency exception

ChromaDB 0.4.22 currently has two published server-authorization advisories with no
patched stable release: CVE-2026-45830 and CVE-2026-45833. This repository uses only
the embedded `PersistentClient`; it does not deploy a Chroma server, HTTP client,
port, container, or tenant API, and reset is disabled. The affected authenticated
server endpoints are therefore outside the deployed boundary.

The exact package/version/IDs and compensating controls are machine checked in
`security/pip-audit-exceptions.json`. The exception expires on 2026-09-30; CI fails
closed after that date or if the dependency pin changes. Before expiry, upgrade to
the first audited fixed stable release or replace the embedded store. This exception
is not a claim that the dependency has no vulnerability.

Never expose the sidecar directly to the public Internet. Put remote access behind
an authenticated TLS reverse proxy and network allow-list.
