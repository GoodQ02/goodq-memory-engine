<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-09-30 -->

# HuggingFace CLI Login Guide

Verification scope: offline checks and source resolution only; this date does
not attest current authentication or gated-model access.

## Purpose

This guide explains how to configure a persistent HuggingFace token for the WSL audio and model-serving stacks without baking user-specific account details into the repo.

## Recommended Pattern

Use:
- `HF_TOKEN` as the primary credential source
- `hf auth login` as an optional local cache/fallback

That keeps automation deterministic while still letting HuggingFace tools work interactively.

## When You Need This

Run this setup if you need access to:
- gated PyAnnote models for diarization
- gated Whisper or other HuggingFace-hosted models
- HuggingFace CLI commands from WSL

## Step 1: Get a Token

1. Visit `https://huggingface.co/settings/tokens`
2. Create or copy a token with read access to the gated repos you are allowed to use
3. Keep the token out of tracked files and logs

## Step 2: Choose a Storage Method

### Option A: Environment Variable

Recommended for automation and repeatable local setup.

Typical locations:
- `.env.local`
- WSL shell profile
- Windows environment passed into WSL

Example:

```bash
# Provision HF_TOKEN through the approved local secret store.
# Do not paste a credential into a shell command or tracked file.
```

### Option B: HuggingFace CLI Cache

Recommended when you want HuggingFace tooling to manage the token directly.

```bash
hf auth login
```

Token cache location:

```text
~/.cache/huggingface/token
```

### Option C: Both

Also acceptable. The environment variable remains the deterministic source; the CLI cache acts as a fallback for local tooling.

## Step 3: Login from WSL

If you are working from the WSL audio environment:

```bash
source ~/goodq_audio/setup_cuda_env.sh
hf auth login
```

Legacy command still works if needed:

```bash
huggingface-cli login
```

## Step 4: Check Presence Without Authentication

Run this offline check in the environment you intend to use. It reports only
whether each variable has a nonempty value; it does not load configuration,
read saved credentials, authenticate, or prove validity or model access.

```bash
python3 -c "import os; print('HF_TOKEN present:', bool(os.environ.get('HF_TOKEN'))); print('PYANNOTE_TOKEN present:', bool(os.environ.get('PYANNOTE_TOKEN'))); print('HUGGINGFACE_TOKEN present:', bool(os.environ.get('HUGGINGFACE_TOKEN')))"
```

From PowerShell, report presence without printing values:

```powershell
'HF_TOKEN', 'PYANNOTE_TOKEN', 'HUGGINGFACE_TOKEN' | ForEach-Object {
    '{0} present: {1}' -f $_, (-not [string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($_, 'Process')))
}
```

Never print a token, its prefix, or a process's complete environment. Do not
use a login or model-download command as a presence check. `hf auth whoami`
is a separate network authentication test, appropriate only when intended;
it was not run for the September 30 audit.

## Token Resolution Model

There is no single precedence across all GoodQ consumers. See the
[configuration loading contract](../../architecture/CONFIG_LOADING_CONTRACT.md#4b-hugging-face-token-aliases)
for the source-verified order. Keep aliases consistent in the approved local
store: a nonempty conflicting alias is not overwritten by normalization.

The worker setup script sources its `.goodq_env` before resolving aliases and
saved-login fallback. Sourcing that script can therefore change bindings;
do not source it merely to inspect the current shell. Windows variable
presence does not establish the environment of an already running WSL worker.

## Required Model Agreements

If diarization is part of your workload, make sure the HuggingFace account behind your token has accepted the relevant gated model agreements, for example:
- `https://huggingface.co/pyannote/speaker-diarization-3.1`
- `https://huggingface.co/pyannote/speaker-diarization-community-1`

## Troubleshooting

### Check Environment Token

```bash
python3 -c "import os; print('HF_TOKEN present:', bool(os.environ.get('HF_TOKEN')))"
```

### Check CLI Identity

```bash
hf auth whoami
```

### Check Python Environment Presence

```bash
python3 -c "import os; print('HF_TOKEN present:', bool(os.environ.get('HF_TOKEN')))"
```

### Logout

```bash
hf auth logout
```

### Re-login

```bash
hf auth login
```

## Commands Reference

```bash
# Check current identity
hf auth whoami

# Login interactively
hf auth login

# Login interactively; avoid credential-bearing command-line arguments
hf auth login

# Logout
hf auth logout

# Inspect environment token presence
python3 -c "import os; print('HF_TOKEN present:', bool(os.environ.get('HF_TOKEN')))"
```
