# Secrets Env Migration (One-Time)

This repo now reads runtime credentials from `.env.local` instead of tracked files.

## Move values into `.env.local`

- `configs/config.yaml` `home_assistant.token` -> `HA_TOKEN`
- `wsl2_audio/config.json` `huggingface_token` -> `PYANNOTE_TOKEN` (or `HF_TOKEN`)

## Minimal `.env.local` template

```env
HA_TOKEN=replace_with_home_assistant_token
PYANNOTE_TOKEN=replace_with_huggingface_or_pyannote_token
HF_TOKEN=replace_with_huggingface_token
```

Notes:
- `.env.local` is already gitignored.
- `wsl2_audio/config.json` now supports `${ENV_VAR}` references and `huggingface_token_env`.
