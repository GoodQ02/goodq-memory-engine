# HuggingFace CLI Login Guide - Token Setup

## Summary

Use this guide to configure a local Hugging Face token for gated model downloads in
WSL. It is written for a fresh machine and does not assume an existing token state.

## Example Healthy State

```
✓ Logged in as: <your_huggingface_username>
✓ HF_TOKEN in environment: <from .env.local or shell profile>
✓ HF_HOME configured: <GOODQ_MODEL_CACHE>
✓ Token accessible via HuggingFace CLI
```

## How Your Token is Currently Managed

### 1. Environment Variable (Primary)
Set `HF_TOKEN` in your shell environment, for example in:
- `~/.bashrc`
- `~/.bash_profile`
- `~/.profile`
- Windows environment (passed to WSL)

### 2. HuggingFace CLI (Secondary/Fallback)
You can also log in via `huggingface-cli`, which stores the token in the local HF cache.

## When to Use `hf auth login`

Use this command if you want to:
1. **Update/refresh your token** (e.g., generated a new one)
2. **Switch to a different HuggingFace account**
3. **Store token in HF cache** (instead of environment variable)
4. **Share token across multiple environments** (same user, different shells)

## How to Login (Step-by-Step)

### Preparation

1. **Get your token:**
   - Visit: https://huggingface.co/settings/tokens
   - Click: "Create new token" OR copy existing token
   - Scope: "Read access to contents of all public gated repos you can access"
   - Copy the token (starts with `hf_...`)

### Login Command

```bash
# Activate the environment first
source ~/goodq_audio/setup_cuda_env.sh

# Use the NEW command (recommended)
hf auth login

# OR use the OLD command (still works)
huggingface-cli login
```

### Interactive Process

```
_|    _|  _|    _|    _|_|_|    _|_|_|  _|_|_|  _|      _|    _|_|_|
[HuggingFace ASCII art]

A token is already saved on your machine.
Setting a new token will erase the existing one.

Enter your token (input will not be visible): [paste token here]

Add token as git credential? (Y/n) Y
  
Token is valid (permission: read).
Your token has been saved to ~/.cache/huggingface/token
Login successful
```

### After Login

Verify:
```bash
hf auth whoami
# Output: user: <your_huggingface_username>
```

Test:
```bash
python3 ~/goodq_audio/check_hf_token.py
```

## Token Storage Locations

### Via HF CLI Login
```
Location: ~/.cache/huggingface/token
Permissions: 600 (readable only by you)
Format: Plain text file with token
```

### Via Environment Variable
```
Location: Your shell config (~/.bashrc, etc.)
Format: export HF_TOKEN="hf_..."
Visibility: Available to all processes in that shell
```

## How setup_cuda_env.sh Handles Tokens

The script is smart about token management:

```bash
# Priority 1: Use existing HF_TOKEN from environment
if [ -n "$HF_TOKEN" ]; then
    export HUGGINGFACE_TOKEN="$HF_TOKEN"
    
# Priority 2: Fall back to HF CLI stored token
else
    RETRIEVED_TOKEN=$(python3 -c "from huggingface_hub import HfFolder; ...")
    export HF_TOKEN="$RETRIEVED_TOKEN"
    export HUGGINGFACE_TOKEN="$RETRIEVED_TOKEN"
fi
```

**Result:** It doesn't matter which method you use - the script will find your token!

## Recommended Setup (Choose One)

### Option A: Environment Variable

**Pros:**
- Token available across all shells/sessions
- No need to login via HF CLI
- Works with WSL environment variables from Windows

**Setup:**
Store `HF_TOKEN` in your local shell configuration or `.env.local`.

### Option B: HF CLI Login Only

**Pros:**
- Token managed by HuggingFace tools
- Easy to update (just run `hf auth login` again)
- Automatic permission management

**Setup:**
```bash
# Remove from environment (optional)
unset HF_TOKEN
unset HUGGINGFACE_TOKEN

# Login via CLI
source ~/goodq_audio/setup_cuda_env.sh
hf auth login
[paste your token]
```

### Option C: Both (Belt and Suspenders)

**Pros:**
- Maximum reliability
- Falls back gracefully

**Setup:**
Keep both if you want an environment-variable primary path with CLI fallback.

## Recommended Setup

The most portable setup is:
1. `HF_TOKEN` in your local environment
2. optional `hf auth login` fallback
3. `setup_cuda_env.sh` handling either source automatically

What you still need to do on a new machine:
1. configure a valid token
2. accept any upstream gated-model agreements you plan to use

Common gated-model examples:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/speaker-diarization-community-1

## Troubleshooting

### To check where your token comes from:
```bash
# Check environment
echo $HF_TOKEN

# Check HF CLI
hf auth whoami

# Check Python access
python3 -c "from huggingface_hub import HfFolder; print(HfFolder.get_token()[:10])"
```

### To logout:
```bash
hf auth logout
```

### To re-login:
```bash
hf auth login
```

## Commands Reference

```bash
# Check who you're logged in as
hf auth whoami

# Login (interactive)
hf auth login

# Login (non-interactive)
hf auth login --token YOUR_TOKEN_HERE

# Logout
hf auth logout

# Check token in environment
echo $HF_TOKEN

# Full diagnostic
python3 ~/goodq_audio/check_hf_token.py
```

## Security Best Practices

1. **Never commit tokens to git**
2. **Use token with minimal required permissions** (read-only for gated repos)
3. **Regenerate tokens periodically**
4. **Don't share tokens** (each user should have their own)
5. **Use environment variables for automation** (like your Windows pipeline)

## Next Steps

1. Configure `HF_TOKEN` locally
2. Accept any required upstream model agreements
3. Verify access with:
```bash
python3 ~/goodq_audio/check_hf_token.py
```
