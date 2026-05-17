# GoodQ4All Support

GoodQ4All is a local-first public preview. The fastest way to get useful help is
to route the question to the narrowest public surface and redact local details
before posting.

## Where to Start

- First install or one-file ingestion trouble: read
  [`docs/guides/FIRST_RUN.md`](docs/guides/FIRST_RUN.md), then use the
  **First-Run Problem** issue template if the problem persists.
- Reproducible runtime or documentation bug: use the **Bug Report** issue
  template.
- Scoped product or documentation idea: use the **Feature Request** issue
  template.
- General questions, operator notes, and community discussion: use
  [GitHub Discussions](https://github.com/GoodQ02/goodq4all/discussions).
- Suspected vulnerability: do not open a public issue. Follow
  [`SECURITY.md`](SECURITY.md).
- Conduct or safety concern: follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Before You Post

Please remove:

- API keys, tokens, and local secrets
- private file paths and usernames
- private media names, transcripts, screenshots, and logs
- local network details
- generated runtime databases or memory artifacts

Useful reports include:

- the commit SHA or release tag tested
- the exact command or documented step that failed
- the smallest redacted console or log excerpt that explains the failure
- host profile (`BASELINE`, `GPU_ENHANCED`, or `Unsure`)
- which step still worked before the failure

## Support Boundaries

The supported public path is Windows-first, local-first, and pre-1.0. The public
preview does not promise a hosted service, polished product UI, healthcare or
regulatory readiness, autonomous mutation/control behavior, or support for
private media/corpus packs in the base installer.
