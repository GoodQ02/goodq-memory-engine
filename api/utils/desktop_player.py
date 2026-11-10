"""One local, owned VLC window; originals and the user's VLC session remain untouched."""
from __future__ import annotations

import atexit
import base64
import ctypes
from ctypes import wintypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlencode


class DesktopPlayerError(RuntimeError):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def find_vlc() -> Path | None:
    """Prefer the offline installer payload; never accept an executable from a request."""
    if os.name != "nt":
        return None
    candidates = [Path(__file__).resolve().parents[2] / "vlc" / "vlc.exe"]
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "VideoLAN" / "VLC" / "vlc.exe")
    return next((path for path in candidates if path.is_file()), None)


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def fit_window(geometry, work_area):
    left, top, right, bottom = work_area
    width = min(max(320, geometry["width"]), right - left)
    height = min(max(240, geometry["height"]), bottom - top)
    return dict(x=max(left, min(geometry["x"], right - width)),
                y=max(top, min(geometry["y"], bottom - height)), width=width, height=height)


class NativeVLC:
    """VLC's supported HTTP control, private password and loopback binding per child."""
    def __init__(self, executable: Path):
        self._profile = tempfile.TemporaryDirectory(prefix="goodq-vlc-")
        # Windows VLC obtains Qt's config root through the shell, not APPDATA.
        # Its supported portable directory is relative to vlc.exe. Copy only
        # that unmodified small launcher; DLLs/plugins remain in the runtime.
        executable = executable.resolve()
        launch_path = Path(self._profile.name) / "vlc.exe"
        try:
            (launch_path.parent / "portable").mkdir()
            source_hash = hashlib.sha256(executable.read_bytes()).digest()
            shutil.copyfile(executable, launch_path)
            if hashlib.sha256(launch_path.read_bytes()).digest() != source_hash:
                raise DesktopPlayerError("VLC launcher changed while preparing its private session")
        except Exception:
            self._profile.cleanup()
            raise
        self._password = secrets.token_urlsafe(32)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self._port = reservation.getsockname()[1]
        self._authorization = "Basic " + base64.b64encode((":" + self._password).encode()).decode()
        environment = os.environ.copy()
        # Only this child receives the DLL search path; system/user PATH is unchanged.
        environment.update(APPDATA=self._profile.name, LOCALAPPDATA=self._profile.name)
        environment["PATH"] = str(executable.parent) + os.pathsep + environment.get("PATH", "")
        arguments = [str(launch_path), "--ignore-config", "--no-one-instance",
                     "--no-one-instance-when-started-from-file", "--intf=qt", "--extraintf=http",
                     "--http-host=127.0.0.1", f"--http-port={self._port}",
                     f"--http-password={self._password}", "--no-media-library",
                     "--no-metadata-network-access", "--no-qt-privacy-ask", "--no-qt-updates-notif",
                     "--no-qt-recentplay", "--no-qt-video-autoresize", "--no-qt-system-tray",
                     "--no-video-title-show", "--no-fullscreen", "--no-video-on-top",
                     "--no-loop", "--no-repeat", "--no-random"]
        try:
            self.process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, env=environment,
                                            cwd=self._profile.name,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._configure_window_api()
            deadline = time.monotonic() + 10
            while self.alive() and time.monotonic() < deadline:
                try:
                    self.read()
                    return
                except (OSError, ValueError, http.client.HTTPException):
                    time.sleep(0.1)
            raise DesktopPlayerError("VLC did not become ready; no playback was confirmed")
        except Exception:
            self.close()
            raise

    @property
    def pid(self):
        return self.process.pid

    def alive(self):
        return hasattr(self, "process") and self.process.poll() is None

    def _request(self, **query):
        if not self.alive():
            raise DesktopPlayerError("The desktop player was closed")
        # Direct HTTPConnection deliberately ignores proxy environment variables.
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=2)
        try:
            target = "/requests/status.json" + ("?" + urlencode(query) if query else "")
            connection.request("GET", target, headers={"Authorization": self._authorization})
            response = connection.getresponse()
            if response.status != 200:
                raise DesktopPlayerError("VLC control is unavailable")
            payload = response.read(2 * 1024 * 1024 + 1)
            if len(payload) > 2 * 1024 * 1024:
                raise DesktopPlayerError("VLC returned an invalid status")
            return json.loads(payload)
        finally:
            connection.close()

    def read(self):
        return self._request()

    def play(self, path: Path, start: float, playback_id: str):
        self._request(command="pl_empty")
        # A generated item name binds later status to this exact accepted play.
        self._request(command="in_play", input=path.as_uri(), option=f"start-time={start:.6f}",
                      name=f"GoodQ-{playback_id}")

    def stop(self):
        self._request(command="pl_stop")

    def _configure_window_api(self):
        api = self._user32
        api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        api.IsWindowVisible.argtypes = [wintypes.HWND]
        api.IsIconic.argtypes = [wintypes.HWND]
        api.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
        api.GetWindow.restype = wintypes.HWND
        api.MonitorFromRect.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD]
        api.MonitorFromRect.restype = wintypes.HANDLE
        api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)]
        api.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
        api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        api.SetForegroundWindow.argtypes = [wintypes.HWND]
        api.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    def _window(self):
        if not self.alive():
            return None
        matches = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def visit(handle, _):
            pid = wintypes.DWORD()
            self._user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
            if (pid.value == self.pid and self._user32.IsWindowVisible(handle)
                    and not self._user32.GetWindow(handle, 4)):
                name = ctypes.create_unicode_buffer(256)
                self._user32.GetClassNameW(handle, name, len(name))
                if name.value == "Qt5QWindowIcon":
                    matches.append(handle)
            return True

        self._user32.EnumWindows(visit, 0)
        return matches[0] if matches else None

    def geometry(self):
        handle = self._window()
        rect = wintypes.RECT()
        # Window-placement rectangles use workspace coordinates; MoveWindow takes
        # screen coordinates. Keep the latest actual normal rectangle instead.
        if handle and not self._user32.IsIconic(handle) and self._user32.GetWindowRect(handle, ctypes.byref(rect)):
            return dict(x=rect.left, y=rect.top, width=rect.right - rect.left, height=rect.bottom - rect.top)
        return None

    def show(self, geometry=None):
        deadline = time.monotonic() + 3
        handle = self._window()
        while handle is None and self.alive() and time.monotonic() < deadline:
            time.sleep(0.05)
            handle = self._window()
        if handle is None:
            raise DesktopPlayerError("VLC opened without a desktop window")
        self._user32.ShowWindow(handle, 9)  # SW_RESTORE, never topmost/fullscreen.
        if geometry:
            rect = wintypes.RECT(geometry["x"], geometry["y"], geometry["x"] + geometry["width"],
                                 geometry["y"] + geometry["height"])
            monitor = self._user32.MonitorFromRect(ctypes.byref(rect), 2)
            info = _MonitorInfo(cbSize=ctypes.sizeof(_MonitorInfo))
            if not self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                raise DesktopPlayerError("The desktop work area could not be determined")
            area = info.rcWork
            fitted = fit_window(geometry, (area.left, area.top, area.right, area.bottom))
            self._user32.MoveWindow(handle, fitted["x"], fitted["y"], fitted["width"], fitted["height"], True)
        self._user32.SetForegroundWindow(handle)

    def minimize(self):
        handle = self._window()
        if handle:
            self._user32.ShowWindow(handle, 6)

    def close(self):
        if self.alive():
            handle = self._window() if hasattr(self, "_user32") else None
            if handle:
                self._user32.PostMessageW(handle, 0x0010, 0, 0)  # WM_CLOSE, own child only.
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=3)
        self._profile.cleanup()


class DesktopPlayer:
    def __init__(self, *, factory=NativeVLC, resolver=find_vlc, clock=time.monotonic,
                 idle_seconds=300, background=True):
        self._factory, self._resolver, self._clock = factory, resolver, clock
        self._idle_seconds, self._background = idle_seconds, background
        self._lock = threading.RLock()
        self._native = None
        self._geometry = None
        self._idle_since = None
        self._started = 0
        self._start_seconds = 0
        self._playback_confirmed = False
        self._stop_event = threading.Event()
        self._thread = None
        self._state = dict(state="idle", playback_id=None, video_id=None, scene_id=None,
                           time_seconds=None, duration_seconds=None, playing=False, error=None,
                           decoded_video_frames=None, displayed_video_frames=None, pid=None)
        atexit.register(self.close)

    def status(self):
        # A GET neither launches nor sends commands to VLC.
        with self._lock:
            return {"available": self._resolver() is not None, **self._state}

    def play(self, path, start, video_id, scene_id, window=None):
        with self._lock:
            executable = self._resolver()
            if executable is None:
                raise DesktopPlayerError("VLC is not installed on this Windows computer")
            if not self._native or not self._native.alive():
                if self._native:
                    self._native.close()
                try:
                    self._native = self._factory(executable)
                except Exception as exc:
                    self._state.update(state="error", playing=False, error="VLC could not start")
                    raise DesktopPlayerError("VLC could not start") from exc
                geometry = self._geometry or window or dict(x=40, y=40, width=480, height=360)
            else:
                self._geometry = self._native.geometry() or self._geometry
                geometry = None
            playback_id = secrets.token_hex(16)
            self._state.update(state="starting", playback_id=playback_id, video_id=video_id, scene_id=scene_id,
                               time_seconds=None, duration_seconds=None, playing=False, error=None,
                               decoded_video_frames=None, displayed_video_frames=None, pid=self._native.pid)
            self._idle_since = None
            self._started, self._start_seconds = self._clock(), start
            self._playback_confirmed = False
            try:
                self._native.play(path, start, playback_id)
                self._native.show(geometry)
            except Exception as exc:
                self._fail("VLC could not open the original video")
                raise DesktopPlayerError(self._state["error"]) from exc
            if self._background and (self._thread is None or not self._thread.is_alive()):
                self._stop_event.clear()
                self._thread = threading.Thread(target=self._monitor, name="goodq-desktop-player", daemon=True)
                self._thread.start()
            return self.status()

    def done(self, playback_id):
        with self._lock:
            if playback_id != self._state["playback_id"]:
                raise DesktopPlayerError("This playback has been replaced", 409)
            if self._native and self._native.alive():
                try:
                    self._native.stop()
                    self._geometry = self._native.geometry() or self._geometry
                    self._native.minimize()
                except Exception as exc:
                    self._fail("VLC did not acknowledge stopping playback")
                    raise DesktopPlayerError(self._state["error"]) from exc
            self._state.update(state="stopped", playing=False)
            self._idle_since = self._clock()
            return self.status()

    def _fail(self, message):
        self._state.update(state="error", playing=False, error=message)
        if self._native:
            self._native.close()
            self._native = None
        self._state["pid"] = None

    def tick(self):
        """Called only by the worker created through an accepted play operation."""
        with self._lock:
            if self._native is None:
                return
            if not self._native.alive():
                self._native.close()
                self._native = None
                self._state.update(state="closed", playing=False, pid=None)
                return
            try:
                self._geometry = self._native.geometry() or self._geometry
                data = self._native.read()
                current = data.get("information", {}).get("category", {}).get("meta", {}).get("title")
                # Ignore status from the previous input while VLC switches items.
                meta = data.get("information", {}).get("category", {}).get("meta", {})
                belongs = f"GoodQ-{self._state['playback_id']}" in (current, meta.get("filename"))
                if self._idle_since is not None:
                    if belongs and data.get("state") in ("playing", "paused"):
                        self._idle_since = None
                    else:
                        if self._clock() - self._idle_since >= self._idle_seconds:
                            self._native.close()
                            self._native = None
                            self._state.update(state="closed", playing=False, pid=None)
                        return
                duration = data.get("length", 0)
                if belongs and isinstance(duration, (int, float)) and duration > 0:
                    # VLC's HTTP length truncates fractional seconds.
                    if self._start_seconds >= duration + 1:
                        self._fail("Scene timestamp is outside the original video's duration")
                        return
                    self._state["duration_seconds"] = duration
                state = data.get("state")
                if belongs and state in ("playing", "paused"):
                    stats = data.get("stats") or {}
                    frames = stats.get("displayedpictures", 0)
                    position = data.get("time")
                    confirmed = self._playback_confirmed or (
                        isinstance(frames, (int, float)) and frames > 0
                        and isinstance(position, (int, float))
                        and position >= self._start_seconds - 1)
                    self._playback_confirmed = confirmed
                    self._state.update(state=state if confirmed else "starting", playing=confirmed and state == "playing", time_seconds=data.get("time"),
                                       decoded_video_frames=stats.get("decodedvideo"),
                                       displayed_video_frames=stats.get("displayedpictures"))
                elif state == "stopped" and self._state["state"] in ("playing", "paused"):
                    # VLC's HTTP state conflates EOF and the user's Stop button.
                    self._state.update(state="stopped", playing=False)
                    self._native.minimize()
                    self._idle_since = self._clock()
                if self._clock() - self._started > 15 and self._state["state"] == "starting":
                    self._fail("VLC did not confirm playback of the selected original")
            except Exception:
                self._fail("VLC playback status became unavailable")

    def _monitor(self):
        while not self._stop_event.wait(0.5):
            self.tick()
            with self._lock:
                if self._native is None:
                    self._thread = None
                    return

    def close(self):
        self._stop_event.set()
        with self._lock:
            if self._native is not None:
                self._geometry = self._native.geometry() or self._geometry
                self._native.close()
                self._native = None
            self._state.update(state="closed", playing=False, pid=None)
