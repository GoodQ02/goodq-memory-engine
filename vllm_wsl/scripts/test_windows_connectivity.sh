#!/bin/bash
# Windows Connectivity Diagnostic
# Tests if Windows can reach WSL vLLM servers

echo "═══════════════════════════════════════════════════════════════"
echo "🔍 Windows → WSL Connectivity Diagnostic"
echo "═══════════════════════════════════════════════════════════════"
echo ""

echo "1. WSL Network Configuration"
echo "─────────────────────────────────────────────────────────────"
echo "WSL IP Address:"
hostname -I | awk '{print "  " $1}'

echo ""
echo "Listening ports:"
ss -tlnp 2>&1 | grep -E ":(8003|31434)" | awk '{print "  " $4 " " $7}'

echo ""
echo "2. Port 8003 Test (vLLM)"
echo "─────────────────────────────────────────────────────────────"
if curl -s --max-time 2 http://localhost:8003/v1/models >/dev/null 2>&1; then
    echo "  ✅ WSL → localhost:8003 WORKS"
else
    echo "  ❌ WSL → localhost:8003 FAILS"
fi

WSL_IP=$(hostname -I | awk '{print $1}')
if curl -s --max-time 2 http://$WSL_IP:8003/v1/models >/dev/null 2>&1; then
    echo "  ✅ WSL → $WSL_IP:8003 WORKS"
else
    echo "  ❌ WSL → $WSL_IP:8003 FAILS"
fi

if curl -s --max-time 2 http://0.0.0.0:8003/v1/models >/dev/null 2>&1; then
    echo "  ✅ WSL → 0.0.0.0:8003 WORKS"
else
    echo "  ❌ WSL → 0.0.0.0:8003 FAILS"
fi

echo ""
echo "3. Port 31434 Test (Ollama)"
echo "─────────────────────────────────────────────────────────────"
if curl -s --max-time 2 http://localhost:31434/v1/models >/dev/null 2>&1; then  
    echo "  ✅ WSL → localhost:31434 WORKS"
else
    echo "  ❌ WSL → localhost:31434 FAILS"
fi

echo ""
echo "4. Windows Testing Commands"
echo "─────────────────────────────────────────────────────────────"
echo "From Windows PowerShell, run these tests:"
echo ""
echo "  # Test vLLM"
echo "  curl http://localhost:8003/v1/models"
echo ""
echo "  # Test Ollama"  
echo "  curl http://localhost:31434/v1/models"
echo ""
echo "  # If localhost doesn't work, try WSL IP:"
echo "  curl http://$WSL_IP:8003/v1/models"
echo ""

echo "5. WSL Configuration Check"
echo "─────────────────────────────────────────────────────────────"
if [ -f /etc/wsl.conf ]; then
    echo "  /etc/wsl.conf exists:"
    cat /etc/wsl.conf | grep -v "^#" | grep -v "^$" | sed 's/^/    /'
else
    echo "  ⚠️ /etc/wsl.conf NOT FOUND"
fi

echo ""
if [ -f /mnt/c/Users/jdben/.wslconfig ]; then
    echo "  C:\\Users\\jdben\\.wslconfig exists:"
    cat /mnt/c/Users/jdben/.wslconfig | grep -v "^#" | grep -v "^$" | sed 's/^/    /'
else
    echo "  ⚠️ C:\\Users\\jdben\\.wslconfig NOT FOUND"
fi

echo ""
echo "6. Firewall Status"
echo "─────────────────────────────────────────────────────────────"
echo "  Checking if vLLM is bound to all interfaces..."
if ss -tlnp 2>&1 | grep -q "0.0.0.0:8003"; then
    echo "  ✅ vLLM bound to 0.0.0.0:8003 (accessible from Windows)"
else
    echo "  ❌ vLLM NOT bound to 0.0.0.0 (Windows can't reach it)"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "💡 Troubleshooting Tips"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "If Windows can't connect:"
echo "  1. Restart WSL: wsl --shutdown (from Windows)"
echo "  2. Check Windows firewall"
echo "  3. Verify .wslconfig has networkingMode=mirrored"
echo "  4. Try WSL IP directly: http://$WSL_IP:8003/v1/models"
echo ""
