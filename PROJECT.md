# Project: WSL2 Gated Models Migration (Sprint B2)

## Architecture
WSL2 Audio Processing Lane connects to the Windows UCF ingestion pipeline. Gated models (PyAnnote diarization, Wav2Vec2 emotion, Wav2Vec2 audio embedder) must run in offline mode (local-first cache loading), governed by local configuration with zero network reachability during normal execution. Tokens (HF_TOKEN) are securely propagated and redacted in all logs.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | WSL2 Audio Model Audit & Inventory | Audit files and create `wsl2_audio_model_inventory.md` | None | DONE (Conv ID: 79c0ec7b-d4ef-409b-be9f-f71e50e0ef7b) |
| 2 | Offline Isolation & Loader Refactoring | Local-first loading, token propagation & redaction, cache mapping | M1 | DONE (Conv ID: c2b328b3-4daf-4c05-81cf-0f04d6e304d9) |
| 3 | Verification & Windows UCF Integration | No-network tests, controlled pipeline run, UCF evidence check | M2 | DONE (Conv ID: 2a740f59-77d3-40ea-affc-d48ed1c2abd6) |

## Interface Contracts
### Windows Ingestion ↔ WSL2 Audio Service
- Communication via HTTP bridge / process invocation
- Output artifacts (diarization segments, speaker labels, voice signatures, emotion outputs) must be consumed by Windows UCF pipeline and written to DB.
- Tokens (HF_TOKEN) must be resolved from `.env.local` / config on Windows and propagated securely without being printed in command line or logs.
