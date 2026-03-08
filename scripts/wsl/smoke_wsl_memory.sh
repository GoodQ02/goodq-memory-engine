#!/usr/bin/env bash
#
# One-stop smoke test + light self-heal for GoodQ memory stack on WSL.
# - Verifies env vars, vLLM (38005), Qdrant (6333), FAISS env, FAISS index size
# - Starts Qdrant if down (sudo required)
# - Installs missing python deps in goodq_faiss if needed
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FAISS="goodq_faiss"
QDRANT_PORT=6333
VLLM_PORT=38005
CONDA_BIN="${CONDA_BIN:-$HOME/miniconda3/bin/conda}"
PY_BIN="${PY_BIN:-$HOME/miniconda3/envs/${ENV_FAISS}/bin/python}"

cd "$ROOT"

note() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }

if [[ -x "$PY_BIN" ]]; then
  :
else
  warn "Python env not found at $PY_BIN; set PY_BIN to your goodq_faiss python."
fi

to_wsl_path() {
  local raw_path="$1"
  if [[ "$raw_path" =~ ^([A-Za-z]):[\\/](.*)$ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    local rest="${BASH_REMATCH[2]//\\//}"
    echo "/mnt/${drive}/${rest}"
  else
    echo "$raw_path"
  fi
}

note "Reading canonical paths from config"
readarray -t CFG_PATHS < <("$PY_BIN" - <<PY
import json
import pathlib
import sys

root = pathlib.Path(r"$ROOT")
sys.path.insert(0, str(root))
from steps.common.config_loader import load_configs

cfg = load_configs({})
paths = cfg.get("paths", {})
print(paths.get("models_cache", ""))
print(paths.get("faiss_audio_path", ""))
PY
)
MODELS_CACHE_RAW="${CFG_PATHS[0]:-}"
FAISS_PATH_RAW="${CFG_PATHS[1]:-}"

if [[ -z "${HF_HOME:-}" ]]; then
  export HF_HOME="$(to_wsl_path "$MODELS_CACHE_RAW")"
fi
if [[ -z "${TORCH_HOME:-}" ]]; then
  export TORCH_HOME="$(to_wsl_path "$MODELS_CACHE_RAW")"
fi

note "Checking HF/TORCH cache vars"
echo "HF_HOME=${HF_HOME:-unset}"
echo "TORCH_HOME=${TORCH_HOME:-unset}"

note "Ensuring FAISS env deps (python-dotenv, requests, pyyaml, numpy)"
if ! "$PY_BIN" - <<'PY' >/dev/null 2>&1
import importlib
for mod in ("dotenv","requests","yaml","numpy"):
    importlib.import_module(mod)
PY
then
  if [[ -x "$CONDA_BIN" ]]; then
    warn "Installing missing deps into $ENV_FAISS"
    "$CONDA_BIN" install -n "$ENV_FAISS" -y python-dotenv requests pyyaml numpy >/dev/null || warn "Conda install failed; install deps manually."
  else
    warn "Conda not found; install python-dotenv/requests/pyyaml/numpy into $ENV_FAISS manually."
  fi
fi

echo "FAISS index path: $FAISS_PATH_RAW"

if [[ -n "$FAISS_PATH_RAW" ]]; then
  WSL_FAISS_PATH="$(to_wsl_path "$FAISS_PATH_RAW")"
  if [[ -f "$WSL_FAISS_PATH" ]]; then
    note "FAISS index exists at $WSL_FAISS_PATH"
    "$PY_BIN" - <<PY
import faiss
path = r"$WSL_FAISS_PATH"
try:
    idx = faiss.read_index(path)
    print(f"ntotal={idx.ntotal}")
except Exception as e:
    print(f"error reading index: {e}")
PY
  else
    warn "FAISS index not found at $WSL_FAISS_PATH (ingest to populate, then rerun)"
  fi
else
  warn "faiss_index_path missing in config.yaml"
fi

note "Checking Qdrant on port $QDRANT_PORT"
if curl -sf "http://localhost:${QDRANT_PORT}/collections" >/dev/null; then
  note "Qdrant responding on ${QDRANT_PORT}"
else
  warn "Qdrant not responding; attempting start via sudo"
  sudo sh -c "QDRANT__SERVICE__HTTP_PORT=${QDRANT_PORT} /usr/local/bin/qdrant > /tmp/qdrant.log 2>&1 & echo \$! >/tmp/qdrant.pid"
  sleep 5
  if curl -sf "http://localhost:${QDRANT_PORT}/collections" >/dev/null; then
    note "Qdrant started successfully"
  else
    warn "Qdrant still not responding. See /tmp/qdrant.log"
  fi
fi

note "Checking vLLM on port $VLLM_PORT"
if ! curl -sf "http://localhost:${VLLM_PORT}/v1/models" >/dev/null; then
  warn "vLLM not responding on ${VLLM_PORT} (check systemd: sudo systemctl status vllm-llama1b)"
else
  note "vLLM responding on ${VLLM_PORT}"
fi

note "Checking API memory stats (requires API server running on 30000)"
if curl -sf "http://localhost:30000/api/memory/stats" | python3 -m json.tool >/dev/null 2>&1; then
  curl -s "http://localhost:30000/api/memory/stats" | python3 -m json.tool
else
  warn "API not responding on 30000 (start API server, then rerun for stats)"
fi

note "Smoke test complete."
