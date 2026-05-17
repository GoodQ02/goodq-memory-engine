<!-- DOC_STATUS: GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-17 -->

# Welcome Aboard GoodQ4All

This short onboarding film walks through the first local GoodQ4All procedure: clone the repo, enter the project, run bootstrap install, keep `.env.local` in the project root when using local model/cache configuration, validate the bootstrap, launch GoodQ4All, drop media into the import inbox, and watch ingestion produce proof artifacts.

[![Watch Welcome Aboard GoodQ4All](../../samples/assets/goodq4all-demo-poster.jpg)](https://github.com/GoodQ02/goodq4all/releases/download/demo-final-2026-05-17/GOODQ4ALL_DEMO_FINAL.mp4)

- [Watch the final demo](https://github.com/GoodQ02/goodq4all/releases/download/demo-final-2026-05-17/GOODQ4ALL_DEMO_FINAL.mp4)
- Runtime: `2:06.8`
- SHA256: `695C17AC42208397E370875EF2B14229BF16758EEC0B14350271CD35C38C4780`

## What The Demo Shows

The demo is a guided proof path, not a new product surface. It shows the supported local-first operator loop:

1. Clone the public repo.
2. Enter the project root.
3. Run the bootstrap installer.
4. Keep `.env.local` in the repo root when using local model/cache/provider configuration.
5. Run bootstrap validation.
6. Launch the local API/runtime.
7. Drop a media file into `import_inbox`.
8. Watch GoodQ4All ingest the file and write scene/proof artifacts.

## Commands Shown

```powershell
git clone https://github.com/GoodQ02/goodq4all.git
cd goodq4all
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`

## Related Docs

- [First Run](FIRST_RUN.md)
- [Install Bootstrap](../bootstrap/INSTALL_BOOTSTRAP.md)
- [API Reference](../reference/API.md)

## Safety Notes

- Keep `.env.local` local-only and out of commits.
- GoodQ4All remains local-first; no cloud dependency is required for the supported runtime path.
- The demo does not claim a polished end-user UI. It is an instructional film for the current API, CLI, watchdog, and ingestion surface.
