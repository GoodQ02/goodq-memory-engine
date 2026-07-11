<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-19 -->

# Welcome Aboard GoodQ4All

> [!TIP]
> **Recommended User Setup**: For the easiest path, download and run the [GoodQ4All Standalone Setup Installer](https://github.com/GoodQ02/goodq4all/releases/download/v2.5.7/GoodQ4All_Setup_2.5.7.exe) which does not require Git, Conda, or Python. Refer to the [Installation Guide](../bootstrap/INSTALL_BOOTSTRAP.md).

For developers and advanced operators who want to run the project from source and use the CLI, we preserve the full walk-through demo video below as an alternative installation route.

[![Watch Welcome Aboard GoodQ4All (Developer Alternative Route)](../../samples/assets/goodq4all-demo-poster.jpg)](https://github.com/GoodQ02/.github/releases/download/welcome-aboard-goodq4all-2026-05-17/GOODQ4ALL_DEMO_FINAL.mp4)

- [Watch the final demo (Developer CLI Route)](https://github.com/GoodQ02/.github/releases/download/welcome-aboard-goodq4all-2026-05-17/GOODQ4ALL_DEMO_FINAL.mp4)
- Runtime: `2:06.8`
- SHA256: `695C17AC42208397E370875EF2B14229BF16758EEC0B14350271CD35C38C4780`

## What The Demo Shows

The demo is a guided proof path, not a new product surface. It shows the supported local-first operator loop:

1. Clone the public repo.
2. Enter the project root.
3. Run the bootstrap installer.
4. Keep `.env.local` in the repo root when using local model/cache/provider configuration.
5. Run bootstrap validation.
6. Run `LAUNCH_GOODQ.ps1` to check readiness and open operator monitors.
7. Start Watchdog in one terminal.
8. Drop a media file into `import_inbox`.
9. Start the local API in another terminal.
10. Watch GoodQ4All ingest the file and write scene/proof artifacts.

## Commands Shown

```powershell
git clone https://github.com/GoodQ02/goodq4all.git
cd goodq4all
python scripts/bootstrap_install.py
.\scripts\bootstrap_validate.bat
.\LAUNCH_GOODQ.ps1
```

`LAUNCH_GOODQ.ps1` checks readiness and opens operator monitors. It does not start ingestion by itself.

Start Watchdog in one terminal:

```powershell
conda run --no-capture-output -n goodq_core python -m cli.watchdog
```

Drop one small media file into the configured `import_inbox`, then start the API in another terminal:

```powershell
conda run --no-capture-output -n goodq_core python -m api.server
```

Then open:

- `http://127.0.0.1:30000/api/health/summary`
- `http://127.0.0.1:30000/docs`
- `http://127.0.0.1:30000/ui/operator_console_v1/`

## Visual Play-By-Play

These frames are pulled from the final onboarding film so the commands, narration, and terminal proof stay aligned. Click any frame to enlarge it.

| Step | Type or do this | Demo frame |
| --- | --- | --- |
| 1 | Clone the official source:<br>`git clone https://github.com/GoodQ02/goodq4all.git` | <a href="../../samples/assets/demo-steps/01-clone-official-source.jpg"><img src="../../samples/assets/demo-steps/01-clone-official-source.jpg" alt="Clone the GoodQ4All repository" width="300" /></a> |
| 2 | Enter the project cabin:<br>`cd goodq4all` | <a href="../../samples/assets/demo-steps/02-enter-project-cabin.jpg"><img src="../../samples/assets/demo-steps/02-enter-project-cabin.jpg" alt="Enter the GoodQ4All project folder" width="300" /></a> |
| 3 | Run the bootstrap installer:<br>`python scripts/bootstrap_install.py`<br><sub>CPU-safe first-run variant: `python scripts/bootstrap_install.py --disable-gpu --disable-wsl-audio --skip-model-prefetch`.</sub> | <a href="../../samples/assets/demo-steps/03-bootstrap-installer.jpg"><img src="../../samples/assets/demo-steps/03-bootstrap-installer.jpg" alt="Run the bootstrap installer" width="300" /></a> |
| 4 | Optional local config:<br>keep `.env.local` in the repo root when using local model, cache, or provider settings. | <a href="../../samples/assets/demo-steps/04-env-local-root.jpg"><img src="../../samples/assets/demo-steps/04-env-local-root.jpg" alt="Place env local configuration in the repo root" width="300" /></a> |
| 5 | Validate the bootstrap:<br>`.\scripts\bootstrap_validate.bat` | <a href="../../samples/assets/demo-steps/05-bootstrap-validator.jpg"><img src="../../samples/assets/demo-steps/05-bootstrap-validator.jpg" alt="Run the bootstrap validator" width="300" /></a> |
| 6 | Run the launcher/readiness check:<br>`.\LAUNCH_GOODQ.ps1` | <a href="../../samples/assets/demo-steps/06-launch-goodq.jpg"><img src="../../samples/assets/demo-steps/06-launch-goodq.jpg" alt="Launch GoodQ4All readiness checks" width="300" /></a> |
| 7 | Start Watchdog, then drop one small media file into `import_inbox`:<br>`conda run --no-capture-output -n goodq_core python -m cli.watchdog` | <a href="../../samples/assets/demo-steps/07-watchdog-observes.jpg"><img src="../../samples/assets/demo-steps/07-watchdog-observes.jpg" alt="Watchdog observes the imported media file" width="300" /></a> |
| 8 | Start the API and inspect proof:<br>`conda run --no-capture-output -n goodq_core python -m api.server` | <a href="../../samples/assets/demo-steps/08-proof-recorded.jpg"><img src="../../samples/assets/demo-steps/08-proof-recorded.jpg" alt="Ingestion completes and proof is recorded" width="300" /></a> |

## Related Docs

- [First Run](FIRST_RUN.md)
- [Watchdog Quick Reference](watchdog/WATCHDOG_QUICKREF.md)
- [Install Bootstrap](../bootstrap/INSTALL_BOOTSTRAP.md)
- [API Reference](../reference/API.md)

## Safety Notes

- Keep `.env.local` local-only and out of commits.
- GoodQ4All remains local-first; no cloud dependency is required for the supported runtime path.
- The demo may show the read-only operator console as an inspection surface, but
  it should not imply a polished consumer app or any UI-triggered ingestion.
