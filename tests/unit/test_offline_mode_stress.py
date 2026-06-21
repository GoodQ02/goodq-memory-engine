import pytest
import socket
import urllib.request
import http.client
from tests.unit.test_offline_mode_challenger import NetworkBlockError, block_remote_network

def test_offline_mode_stress_raw_socket(block_remote_network):
    """Verify that raw socket connect to remote host is blocked."""
    with pytest.raises(NetworkBlockError):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 80))

def test_offline_mode_stress_raw_socket_loopback(block_remote_network):
    """Verify that raw socket connect to loopback is allowed (refused/success but not blocked)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 54321))
    except Exception as e:
        assert not isinstance(e, NetworkBlockError)

def test_offline_mode_stress_connect_ex(block_remote_network):
    """Verify behavior of connect_ex (does it bypass the block?)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        res = s.connect_ex(("8.8.8.8", 80))
        # If it returned a value, print/assert it to see if it bypassed.
        print(f"connect_ex returned: {res}")
    except NetworkBlockError:
        print("connect_ex correctly raised NetworkBlockError")

def test_offline_mode_stress_urllib(block_remote_network):
    """Verify that urllib.request blocks remote host attempts."""
    with pytest.raises(NetworkBlockError):
        urllib.request.urlopen("http://8.8.8.8", timeout=1)
        
    with pytest.raises(NetworkBlockError):
        urllib.request.urlopen("http://google.com", timeout=1)

def test_offline_mode_stress_http_client(block_remote_network):
    """Verify that http.client blocks remote connection attempts."""
    with pytest.raises(NetworkBlockError):
        conn = http.client.HTTPConnection("google.com", 80)
        conn.request("GET", "/")
        conn.getresponse()

def test_offline_mode_stress_requests(block_remote_network):
    """Verify that requests library (if available) blocks remote attempts."""
    try:
        import requests
    except ImportError:
        pytest.skip("requests library is not installed in this environment")

    with pytest.raises(NetworkBlockError):
        requests.get("http://8.8.8.8", timeout=1)

    with pytest.raises(NetworkBlockError):
        requests.get("http://google.com", timeout=1)

def test_offline_mode_stress_loopback_libraries(block_remote_network):
    """Verify loopback is allowed for http.client and urllib."""
    # urllib
    try:
        urllib.request.urlopen("http://127.0.0.1:54321", timeout=1)
    except Exception as e:
        # Should raise connection refused or timeout, but NOT NetworkBlockError
        assert not isinstance(e, NetworkBlockError)

    # http.client
    try:
        conn = http.client.HTTPConnection("localhost", 54321)
        conn.request("GET", "/")
        conn.getresponse()
    except Exception as e:
        assert not isinstance(e, NetworkBlockError)
