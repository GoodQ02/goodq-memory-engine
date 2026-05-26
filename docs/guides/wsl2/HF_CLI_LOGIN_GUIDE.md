<!-- DOC_BADGE: OPERATIONAL -->
<!-- DOC_STATUS: ACTIVE_GUIDE -->
<!-- DOC_LAST_VERIFIED: 2026-05-07 -->

# HuggingFace CLI Login Guide

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
export HF_TOKEN="hf_..."
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

## Step 4: Verify

```bash
hf auth whoami
python3 -c "from huggingface_hub import HfFolder; print(bool(HfFolder.get_token()))"
```

If you want a repo-local sanity check from the WSL audio workspace:

```bash
python3 ~/goodq_audio/check_hf_token.py
```

## Token Resolution Model

The WSL helper scripts prefer:
1. `HF_TOKEN` from the environment
2. a token already stored by `hf auth login`

That means either method can work, but `HF_TOKEN` is the best source for predictable automation.

## Required Model Agreements

If diarization is part of your workload, make sure the HuggingFace account behind your token has accepted the relevant gated model agreements, for example:
- `https://huggingface.co/pyannote/speaker-diarization-3.1`
- `https://huggingface.co/pyannote/speaker-diarization-community-1`

## Troubleshooting

### Check Environment Token

```bash
echo $HF_TOKEN
```

### Check CLI Identity

```bash
hf auth whoami
```

### Check Python Access

```bash
python3 -c "from huggingface_hub import HfFolder; token = HfFolder.get_token(); print(bool(token))"
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

# Login non-interactively
hf auth login --token YOUR_TOKEN_HERE

# Logout
hf auth logout

# Inspect environment token presence
echo $HF_TOKEN
```
