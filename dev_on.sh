#!/usr/bin/env bash
# GoodQ4All - Local Agent Mode (Dev On) for Unix/macOS

set -e

# Resolve project root robustly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# Load environment variable files if present
if [ -f .env.local ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ "$line" =~ ^[[:space:]]*$ ]] && continue
        export "$line"
    done < .env.local
fi

# Configurable environment overrides
GOODQ_CONDA_ENV="${GOODQ_CONDA_ENV:-goodq_core}"
QDRANT_PORT="${GOODQ_QDRANT_PORT:-6333}"
API_PORT="${GOODQ_API_PORT:-30000}"

# Resolve log/pid directory
LOGS_DIR="${GOODQ_LOGS_ROOT:-$PROJECT_ROOT/logs}"
mkdir -p "$LOGS_DIR"

API_PID_FILE="$LOGS_DIR/api.pid"
WATCHDOG_PID_FILE="$LOGS_DIR/watchdog.pid"
QDRANT_PID_FILE="$LOGS_DIR/qdrant.pid"

echo "[DEV ON] Starting Unix services for environment: $GOODQ_CONDA_ENV"

# 1. Port Conflict & Cleanup for API Server
if lsof -i :"$API_PORT" -t >/dev/null 2>&1; then
    TARGET_PIDS=$(lsof -i :"$API_PORT" -t)
    for pid in $TARGET_PIDS; do
        # Verify if this process is a GoodQ API server
        if ps -p "$pid" -o args= 2>/dev/null | grep -q -E "api.server|api/server"; then
            echo "[DEV ON] Port $API_PORT is occupied by an existing GoodQ API server (PID: $pid). Terminating it..."
            kill -9 "$pid" 2>/dev/null || true
        else
            echo "[ERROR] Port $API_PORT is occupied by an unrelated process (PID: $pid)."
            echo "Command: $(ps -p "$pid" -o args= 2>/dev/null)"
            echo "Refusing to start API server. Please clear port $API_PORT manually."
            exit 1
        fi
    done
fi

# Cleanup old watchdog process if pid file or cmdline exists
if [ -f "$WATCHDOG_PID_FILE" ]; then
    OLD_WD_PID=$(cat "$WATCHDOG_PID_FILE")
    if ps -p "$OLD_WD_PID" >/dev/null 2>&1 && ps -p "$OLD_WD_PID" -o args= | grep -q "cli.watchdog"; then
        echo "[DEV ON] Terminating stale Watchdog process (PID: $OLD_WD_PID)..."
        kill -9 "$OLD_WD_PID" 2>/dev/null || true
    fi
    rm -f "$WATCHDOG_PID_FILE"
fi

# 2. Check and start Qdrant if needed
QDRANT_RUNNING=0
if lsof -i :"$QDRANT_PORT" -t >/dev/null 2>&1; then
    echo "[DEV ON] Qdrant database is already reachable on port $QDRANT_PORT."
    QDRANT_RUNNING=1
fi

if [ $QDRANT_RUNNING -eq 0 ]; then
    echo "[DEV ON] Qdrant not running on port $QDRANT_PORT. Attempting to start..."
    
    # Try systemd if systemctl is available
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl is-active qdrant >/dev/null 2>&1; then
            echo "[DEV ON] Qdrant service is active via systemd."
            QDRANT_RUNNING=1
        elif systemctl list-unit-files | grep -q qdrant; then
            echo "[DEV ON] Starting Qdrant service via systemd..."
            sudo systemctl start qdrant || true
            if systemctl is-active qdrant >/dev/null 2>&1; then
                QDRANT_RUNNING=1
            fi
        fi
    fi
    
    # Fallback to local or system-wide binary execution in background
    if [ $QDRANT_RUNNING -eq 0 ]; then
        QDRANT_BIN=""
        if [ -f "$PROJECT_ROOT/vendor/qdrant/qdrant" ]; then
            QDRANT_BIN="$PROJECT_ROOT/vendor/qdrant/qdrant"
        elif command -v qdrant >/dev/null 2>&1; then
            QDRANT_BIN="$(command -v qdrant)"
        fi
        
        if [ -n "$QDRANT_BIN" ]; then
            echo "[DEV ON] Starting Qdrant binary in background from: $QDRANT_BIN"
            # Start Qdrant with custom port & host, redirect to log file
            QDRANT__SERVICE__HTTP_PORT="$QDRANT_PORT" \
            QDRANT__SERVICE__HOST="127.0.0.1" \
            QDRANT__TELEMETRY_DISABLED="true" \
            nohup "$QDRANT_BIN" > "$LOGS_DIR/qdrant.log" 2>&1 &
            QDRANT_PID=$!
            echo "$QDRANT_PID" > "$QDRANT_PID_FILE"
            # Wait for it to listen
            for i in {1..10}; do
                if lsof -i :"$QDRANT_PORT" -t >/dev/null 2>&1; then
                    QDRANT_RUNNING=1
                    break
                fi
                sleep 0.5
            done
        else
            echo "[WARN] Qdrant binary not found in vendor/ or system PATH. Ingestion will require an external Qdrant instance."
        fi
    fi
fi

# 3. Start API Server and Ingestion Watchdog
# Resolve conda runner
CONDA_EXE=""
if command -v conda >/dev/null 2>&1; then
    CONDA_EXE="conda"
else
    for path in "$HOME/miniconda3/bin/conda" "$HOME/anaconda3/bin/conda" "/opt/miniconda3/bin/conda" "/usr/local/bin/conda"; do
        if [ -f "$path" ]; then
            CONDA_EXE="$path"
            break
        fi
    done
fi

if [ -n "$CONDA_EXE" ]; then
    echo "[DEV ON] Starting API Server via conda ($GOODQ_CONDA_ENV)..."
    PYTHONPATH="$PROJECT_ROOT" nohup "$CONDA_EXE" run -n "$GOODQ_CONDA_ENV" python -m api.server > "$LOGS_DIR/api.log" 2>&1 &
    echo $! > "$API_PID_FILE"

    echo "[DEV ON] Starting Ingestion Watchdog via conda ($GOODQ_CONDA_ENV)..."
    PYTHONPATH="$PROJECT_ROOT" nohup "$CONDA_EXE" run -n "$GOODQ_CONDA_ENV" python -m cli.watchdog > "$LOGS_DIR/watchdog.log" 2>&1 &
    echo $! > "$WATCHDOG_PID_FILE"
else
    # Fallback to system python3 if conda is missing
    echo "[WARN] Conda not found. Falling back to system python3..."
    if command -v python3 >/dev/null 2>&1; then
        echo "[DEV ON] Starting API Server via system python3..."
        PYTHONPATH="$PROJECT_ROOT" nohup python3 -m api.server > "$LOGS_DIR/api.log" 2>&1 &
        echo $! > "$API_PID_FILE"

        echo "[DEV ON] Starting Ingestion Watchdog via system python3..."
        PYTHONPATH="$PROJECT_ROOT" nohup python3 -m cli.watchdog > "$LOGS_DIR/watchdog.log" 2>&1 &
        echo $! > "$WATCHDOG_PID_FILE"
    else
        echo "[ERROR] Python3 not found on system PATH. Unable to start services."
        exit 1
    fi
fi

echo "[DEV ON] Local agent mode activated."
echo "API Server PID: $(cat "$API_PID_FILE")"
echo "Watchdog PID: $(cat "$WATCHDOG_PID_FILE")"
if [ -f "$QDRANT_PID_FILE" ]; then
    echo "Qdrant PID: $(cat "$QDRANT_PID_FILE")"
fi
