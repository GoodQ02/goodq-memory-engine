#!/usr/bin/env bash
set -u

PORT="${1:-6333}"
PATH_SUFFIX="/collections"

echo "========================================"
echo "WSL Qdrant Reachability Check"
echo "========================================"

WIN_HOST_IP="$(ip route 2>/dev/null | awk '/^default/ {print $3; exit}')"
if [[ -z "${WIN_HOST_IP}" ]]; then
  echo "[FAIL] Could not detect Windows host IP from routing table"
  exit 2
fi

echo "[INFO] Windows host IP: ${WIN_HOST_IP}"
echo "[INFO] Port: ${PORT}"

if timeout 3 bash -lc ":</dev/tcp/${WIN_HOST_IP}/${PORT}" 2>/dev/null; then
  echo "[PASS] TCP ${WIN_HOST_IP}:${PORT} reachable"
  tcp_ok=1
else
  echo "[WARN] TCP ${WIN_HOST_IP}:${PORT} not reachable"
  tcp_ok=0
fi

check_json() {
  local label="$1"
  local url="$2"
  local tmp code body

  tmp="$(mktemp)"
  code="$(curl -sS --max-time 6 -o "$tmp" -w "%{http_code}" "$url" 2>/dev/null || echo 000)"
  body="$(cat "$tmp" 2>/dev/null || true)"
  rm -f "$tmp"

  echo "[CHECK] ${label}: ${url}"
  echo "[INFO] HTTP ${code}"

  if [[ "${code}" =~ ^2[0-9][0-9]$ ]] && printf '%s' "$body" | python3 -c 'import sys,json; json.load(sys.stdin)' >/dev/null 2>&1; then
    echo "[PASS] ${label} returned valid JSON"
    return 0
  fi

  echo "[FAIL] ${label} did not return valid JSON"
  return 1
}

local_ok=0
host_ok=0

check_json "WSL localhost" "http://localhost:${PORT}${PATH_SUFFIX}" && local_ok=1 || true
check_json "Windows host IP" "http://${WIN_HOST_IP}:${PORT}${PATH_SUFFIX}" && host_ok=1 || true

echo "========================================"
echo "WSL Summary"
echo "========================================"
echo "[INFO] tcp_ok=${tcp_ok}"
echo "[INFO] local_ok=${local_ok}"
echo "[INFO] host_ok=${host_ok}"

if [[ "${local_ok}" -eq 1 || "${host_ok}" -eq 1 ]]; then
  exit 0
else
  exit 1
fi