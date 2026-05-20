# GoodQ4All Operator Console v1

Observer-only local runtime console for GoodQ4All.

Preferred launch path:

```powershell
python -m api.server
```

Open:

```text
http://127.0.0.1:30000/ui/operator_console_v1/
```

Static development launch from the repository root:

```powershell
python -m http.server 8000
```

Open:

```text
http://127.0.0.1:8000/ui/operator_console_v1/
```

The console reads from `http://127.0.0.1:30000` by default. Use `?api_base=...`
to point it at another local API base.

For richer local metrics, start the API with optional read-only artifact roots:

```powershell
$env:GOODQ_RUN_REPORTS_ROOT="<local witness reports root>"
$env:GOODQ_CONTROL_RECURRENCE_REPORTS_ROOT="<local recurrence reports root>"
python -m api.server
```

This surface is read-only. It does not trigger ingestion, reindexing, config
healing, report generation, or ControlAgent behavior.

Current panels cover Flight Deck orientation, runtime summary, latest indexed
run, recurrence latest/trend, step-run evidence, temporal/emotion rollups,
graph/store truth, engine diagnostics, GPU/WSL/queue counters, memory stores,
video inventory, selected timeline, scene evidence summaries, media preview,
retrieval handoff, and Justification Channel handoff.

Audio proof is intentionally split:

- latest run evidence uses `/api/runs/latest/evidence` and reports strict
  current-run CLAP/Qdrant proof for the selected indexed run scope
- audio provenance inventory uses `/api/runs/audio-proof/latest` and shows
  run-tagged Qdrant audio payloads as historical inventory until a row matches
  the selected run

Do not interpret the inventory drilldown as current-run proof by itself.
