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

## Hugging Face credential handling

Secrets belong in the approved environment-backed local store or ignored
`.env.local`, never tracked files, terminal output, logs, or command-line
arguments. Report nonempty presence only, without token prefixes, hashes, or
full environment dumps. See the [HF guide](docs/guides/wsl2/HF_CLI_LOGIN_GUIDE.md)
and [alias contract](docs/architecture/CONFIG_LOADING_CONTRACT.md#4b-hugging-face-token-aliases).

### September 30, 2026 bounded audit

The audited public main tip was `fbb89c10793245c2a1d433ba6a2db8e251b2bc90`;
private development tip was `2c13cec6e8b11a74bbbdbf3cf63a88b8851dd76e`.
No production HF credential hardcoding was found in 5,158 public and 5,936
private scanned text files. Current tracked pattern matches were synthetic
redaction-test fixtures and checksum fields. Ignored local environment files
still contained token-shaped bindings; this did not establish a new public leak.

Locally reachable history covered 103 public refs/15,002 blobs and 80 private
refs/15,043 blobs. Sixteen historical credential-candidate blobs across twelve
paths remained reachable from both current branches. Cleanup commits
`f7a7f96c5e57175377ca5857c413d073b85256ea` and
`4ddbd4182716b6e7f9d9702114481387a031e710` removed current-tree material but
did not erase earlier history. In-memory comparison found no exact match
between scanned historical credentials and the current ignored environment
values. No token values or secret-bearing lines were emitted or retained in
reports, and no remote history was fetched.

Selected Windows and running-WSL environment/profile/service checks did not
establish an active HF-dependent audio job. The configured audio distribution
was stopped; its deployed worker environment and saved login remain unverified.
Saved-login checks elsewhere used presence/file metadata only. Presence does
not establish validity, token-label identity, or successful model access.

Coverage excluded oversized blobs (twenty per history), binary current files,
remote-only refs, dangling/reflog-only objects, LFS payloads, other process
environments, unrelated personal stores, and the stopped distribution. The
scanner checked alphanumeric HF token patterns with suffixes of at least twenty
characters plus selected literal assignments; this is bounded evidence, not
a guarantee that no secret exists. Credentials were not tested or changed.

Expired access can affect fresh private/gated downloads and pyannote provisioning.
Complete local caches and offline consumers may continue; no actual access
failure or misuse was established. Core local runtime health is a separate issue.

Maintainer/account decisions still required: confirm affected labels and expiry
from HF account records; authorize replacement only for workflows that need it;
review any conflicting aliases before changing selection behavior; and approve
any stopped-distro inspection that could start services. Reading a WSL UNC
path can start a distribution. History rewrite, credential changes, publication,
and unrecoverable data/history deletion are separate authorized actions.

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
- Public-release boundary: [`docs/releases/PUBLIC_SANITIZATION_MANIFEST.md`](docs/releases/PUBLIC_SANITIZATION_MANIFEST.md)
