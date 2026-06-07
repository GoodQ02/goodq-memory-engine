#!/usr/bin/env bash
# GoodQ4All - Game Mode (Dev Off) for Unix/macOS

set -e

# Resolve project root robustly
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
cd "$PROJECT_ROOT"

# Resolve log/pid directory
LOGS_DIR="${GOODQ_LOGS_ROOT:-$PROJECT_ROOT/logs}"

API_PID_FILE="$LOGS_DIR/api.pid"
WATCHDOG_PID_FILE="$LOGS_DIR/watchdog.pid"
QDRANT_PID_FILE="$LOGS_DIR/qdrant.pid"

echo "[DEV OFF] Deactivating local agent services..."

stop_process() {
    local name="$1"
    local pid_file="$2"
    local pattern="$3"
    local stopped=0

    # 1. Try stopping by PID file first
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if ps -p "$pid" >/dev/null 2>&1; then
            local cmdline
            cmdline=$(ps -p "$pid" -o args= 2>/dev/null)
            if echo "$cmdline" | grep -q "$pattern"; then
                echo "[DEV OFF] Stopping $name (PID: $pid)..."
                kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null
                stopped=1
            else
                echo "[DEV OFF] PID $pid file found but it does not match $name process identity. Leaving alone."
            fi
        fi
        rm -f "$pid_file"
    fi

    # 2. Fall back to safe command-line matching if not stopped via PID file
    if [ $stopped -eq 0 ]; then
        local matching_pids
        matching_pids=$(ps ax -o pid,args | grep "$pattern" | grep -v "grep" | grep -v "dev_off.sh" | awk '{print $1}')
        if [ -n "$matching_pids" ]; then
            for p in $matching_pids; do
                echo "[DEV OFF] Found matching $name process (PID: $p). Stopping..."
                kill "$p" 2>/dev/null || kill -9 "$p" 2>/dev/null
                stopped=1
            done
        fi
    fi

    if [ $stopped -eq 0 ]; then
        echo "[DEV OFF] $name is not running or was not found."
    fi
}

# Stop API Server
stop_process "API Server" "$API_PID_FILE" "api.server"

# Stop Ingestion Watchdog
stop_process "Ingestion Watchdog" "$WATCHDOG_PID_FILE" "cli.watchdog"

# Stop Qdrant if started via wrapper PID file
if [ -f "$QDRANT_PID_FILE" ]; then
    QDRANT_PID=$(cat "$QDRANT_PID_FILE")
    if ps -p "$QDRANT_PID" >/dev/null 2>&1; then
        echo "[DEV OFF] Stopping wrapper-owned Qdrant database (PID: $QDRANT_PID)..."
        kill "$QDRANT_PID" 2>/dev/null || kill -9 "$QDRANT_PID" 2>/dev/null
    else
        echo "[DEV OFF] Wrapper-owned Qdrant database (PID: $QDRANT_PID) was already stopped."
    fi
    rm -f "$QDRANT_PID_FILE"
else
    echo "[DEV OFF] Leaving system-wide/docker Qdrant instance alone (not started by wrapper)."
fi

echo "[DEV OFF] All dev services deactivated and VRAM reclaimed."
echo ""
echo "Processes left running (if any):"
if command -v qdrant >/dev/null 2>&1; then
    ps ax -o pid,args | grep "qdrant" | grep -v "grep" || echo "  None"
else
    echo "  None"
fi
