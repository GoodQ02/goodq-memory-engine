<!-- DOC_BADGE: CANONICAL -->
<!-- DOC_STATUS: AUTHORITATIVE -->
<!-- DOC_LAST_VERIFIED: 2026-07-11 -->

# Security Policy

## Supported Surface

The supported publication and release surface for GoodQ4All is the `main`
branch of the public repository. The canonical public entrypoints are:

- `python scripts/bootstrap_install.py`
- `LAUNCH_GOODQ.ps1`
- `LAUNCH_GOODQ.bat`

Security-sensitive local configuration belongs only in:

- `.env.local`
- `configs/config.local.yaml`

## Security Posture Summary

GoodQ4All is designed around a conservative local-first posture:

- no required cloud dependency for core runtime behavior
- loopback-first defaults for API and Qdrant surfaces
- Windows-native `GoodQ_Qdrant` service as the canonical Qdrant path
- optional integrations only when explicitly configured by the operator
- local persistence as the system of record

## Dependency and Scanning Automation

The public repository uses source-owned GitHub Actions for baseline validation,
documentation drift checks, CodeQL analysis, and dependency review on pull
requests. Dependabot broad version-update pull requests are intentionally
suppressed because GoodQ4All keeps runtime, WSL, CUDA, model, and step-env
dependency lanes pinned. Security advisories and dependency alerts still require
maintainer review before any lockfile, environment, or installer lane changes.

Do not treat an automated dependency bump as safe by default. Dependency
changes that affect runtime lanes should include the relevant bootstrap,
validation, and witness evidence before promotion.

## Reporting a Vulnerability

Please do not open public issues for suspected vulnerabilities.

Preferred path:

- use GitHub private vulnerability reporting for this repository if it is available to you

Fallback path:

- contact the maintainers privately through the email address listed on the repository owner's GitHub profile and include a concise report

Please include:

- affected branch or commit, if known
- the component or entrypoint involved
- reproduction steps
- expected impact
- sanitized logs or screenshots if relevant

Please avoid public disclosure until the maintainers have had a reasonable
opportunity to assess and respond.

## Out of Scope

The following usually do not require a private security report unless they create
a reproducible product vulnerability:

- workstation-specific local misconfiguration
- issues only present in retired or historical surfaces
- upstream model or driver vulnerabilities outside this repository’s shipped surface

## Related Policies

- Support routing: [`SUPPORT.md`](SUPPORT.md)
- Contributor expectations: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- Bootstrap guide: [`docs/bootstrap/INSTALL_BOOTSTRAP.md`](docs/bootstrap/INSTALL_BOOTSTRAP.md)
- Historical shipping profile: [`docs/archive/releases/SHIP_PROFILE.md`](docs/archive/releases/SHIP_PROFILE.md)
