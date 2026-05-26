# HuggingFace CLI Login Guide - Permanent Token Setup

## Summary

You **already have a working HF token** setup! Here's the current state and how to manage it.

## Current Status ✅

```
✓ Logged in as: JoesDomingo
✓ HF_TOKEN in environment: <from .env.local>
✓ HF_HOME configured: /mnt/l/models
✓ Token accessible via HuggingFace CLI
```

## How Your Token is Currently Managed

### 1. Environment Variable (Primary)
Your `HF_TOKEN` is set in your shell environment, probably in:
- `~/.bashrc`
- `~/.bash_profile`
- `~/.profile`
- Windows environment (passed to WSL)

### 2. HuggingFace CLI (Secondary/Fallback)
You're also logged in via `huggingface-cli`, which stores the token in HF's cache.

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
Your token has been saved to /home/joesdomingo/.cache/huggingface/token
Login successful
```

### After Login

Verify:
```bash
hf auth whoami
# Output: user: JoesDomingo
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

### Option A: Environment Variable (Your Current Setup) ✅

**Pros:**
- Token available across all shells/sessions
- No need to login via HF CLI
- Works with WSL environment variables from Windows

**Setup:**
Already done! Your `HF_TOKEN` is in your environment.

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
Keep both! (This is what you have now)

## My Recommendation for You

**Keep your current setup!** You have both:
1. ✅ `HF_TOKEN` in environment (primary)
2. ✅ Logged in via HF CLI (fallback)
3. ✅ `setup_cuda_env.sh` handles both automatically

**What you need to do NOW:**
1. ✅ Token setup: DONE (nothing needed)
2. ⚠️ Accept model agreements: **THIS IS WHAT YOU NEED**
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

Since your token is already properly configured:

1. ✅ Token setup: **COMPLETE** (no action needed)
2. ⚠️ Model access: **PENDING** (accept agreements)
3. ✅ Environment setup: **COMPLETE** (setup_cuda_env.sh works)

**Your only remaining task:**
Accept the pyannote model user agreements, then you're done!

---

**Questions?** Run the diagnostic:
```bash
python3 ~/goodq_audio/check_hf_token.py
```
