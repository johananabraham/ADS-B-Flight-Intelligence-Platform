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

Never expose the sidecar directly to the public Internet. Put remote access behind
an authenticated TLS reverse proxy and network allow-list.
