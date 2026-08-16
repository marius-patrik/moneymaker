"""Service-manager integration: install moneymaker as a background service.

Wraps launchd on macOS and systemd (user units) on Linux behind one command
set, so `moneymaker service install|start|stop|status|uninstall` works the
same on both.

The service runs `serve --prod`: the UI is built once and served by the API
on a single port, so there is no bun process to keep alive and the unit has
exactly one thing to supervise.

User-level services on purpose — no sudo, no system-wide install. On Linux
that means the service stops at logout unless lingering is enabled; the
install step says so rather than silently enabling it.
"""

from __future__ import annotations

import os
import pathlib
import platform
import shutil
import time
import subprocess
import sys
from typing import Optional

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_DEPLOY = _REPO_ROOT / "deploy"

LABEL = "com.moneymaker.server"
UNIT = "moneymaker.service"


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _plist_path() -> pathlib.Path:
    return pathlib.Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _unit_path() -> pathlib.Path:
    return pathlib.Path.home() / ".config" / "systemd" / "user" / UNIT


def _target_path() -> pathlib.Path:
    return _plist_path() if _is_macos() else _unit_path()


def _log_dir(home: str) -> pathlib.Path:
    """
    Where the service writes its logs.

    Creating the directory is best-effort: rendering a unit file should not
    fail just because the data dir isn't reachable yet (a not-yet-mounted
    volume, a path that only exists on the target machine). The service
    manager creates it at start time if it is missing.
    """
    d = pathlib.Path(home) / "logs"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _render(template: pathlib.Path, home: str, host: str, port: int) -> str:
    """Fill the template placeholders with this machine's absolute paths."""
    python = sys.executable
    # The service runs outside a shell, so it inherits no PATH. bun is needed
    # for the --prod UI build; include its usual location plus whatever we have.
    path_parts = [str(pathlib.Path(python).parent), os.environ.get("PATH", "")]
    bun = shutil.which("bun")
    if bun:
        path_parts.insert(0, str(pathlib.Path(bun).parent))
    return (
        template.read_text()
        .replace("__PYTHON__", python)
        .replace("__REPO__", str(_REPO_ROOT))
        .replace("__HOME__", home)
        .replace("__HOST__", host)
        .replace("__PORT__", str(port))
        .replace("__LOGDIR__", str(_log_dir(home)))
        .replace("__PATH__", ":".join(p for p in path_parts if p))
    )


def _run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------- install

def install(home: str, host: str = "127.0.0.1", port: int = 8787,
            start: bool = True) -> None:
    template = _DEPLOY / (f"{LABEL}.plist" if _is_macos() else UNIT)
    if not template.exists():
        raise FileNotFoundError(f"Service template missing: {template}")

    target = _target_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render(template, home, host, port))
    print(f"Wrote {target}")

    if not shutil.which("bun"):
        print("warning: bun is not on PATH — `serve --prod` cannot build the UI.\n"
              "         The API will still run; install bun to get the web UI.",
              file=sys.stderr)

    if _is_macos():
        # bootout first so reinstalling picks up a changed plist.
        _run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
        r = _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(target)])
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
            raise RuntimeError("launchctl bootstrap failed")
        print(f"Loaded {LABEL} (starts at login).")
    else:
        _run(["systemctl", "--user", "daemon-reload"])
        r = _run(["systemctl", "--user", "enable", UNIT])
        if r.returncode != 0:
            print(r.stderr.strip(), file=sys.stderr)
        print(f"Enabled {UNIT} (starts at login).")
        print("Note: user services stop at logout unless lingering is on.\n"
              f"      Enable it with: sudo loginctl enable-linger {os.getlogin()}")

    if start:
        _service_start()
    print(f"\n  Web UI   http://{host}:{port}")
    print(f"  Logs     {_log_dir(home)}/server.log")


def uninstall() -> None:
    target = _target_path()
    if _is_macos():
        _run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
    else:
        _run(["systemctl", "--user", "disable", "--now", UNIT])
        _run(["systemctl", "--user", "daemon-reload"])
    if target.exists():
        target.unlink()
        print(f"Removed {target}")
    else:
        print("Service was not installed.")


# ------------------------------------------------------------ start/stop

def _domain() -> str:
    return f"gui/{os.getuid()}"


def _wait_until(predicate, timeout: float = 20.0, interval: float = 0.4) -> bool:
    """Poll until predicate() is true. Returns False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _is_loaded() -> bool:
    if _is_macos():
        return _run(["launchctl", "print", f"{_domain()}/{LABEL}"]).returncode == 0
    r = _run(["systemctl", "--user", "is-active", UNIT])
    return r.stdout.strip() == "active"


def _service_start() -> None:
    target = _target_path()
    if not target.exists():
        raise RuntimeError("Service is not installed — run `moneymaker service install`.")
    if _is_macos():
        # bootstrap loads the job and RunAtLoad starts it. If it is already
        # loaded, kickstart is the way to get it running.
        if _is_loaded():
            _run(["launchctl", "kickstart", f"{_domain()}/{LABEL}"])
        else:
            _run(["launchctl", "bootstrap", _domain(), str(target)])
    else:
        _run(["systemctl", "--user", "start", UNIT])
    print("Started.")


def _service_stop(quiet: bool = False) -> None:
    """
    Fully stop the service and wait for it to go away.

    On macOS `launchctl kill` only signals — KeepAlive then revives the job,
    so a real stop means booting it out of the domain. Waiting matters
    because restart otherwise races the old process for the port.
    """
    if _is_macos():
        _run(["launchctl", "bootout", f"{_domain()}/{LABEL}"])
    else:
        _run(["systemctl", "--user", "stop", UNIT])

    if not _wait_until(lambda: not _is_loaded()):
        print("warning: service did not stop within 20s", file=sys.stderr)
    if not quiet:
        print("Stopped.")


def status() -> None:
    target = _target_path()
    print(f"Definition: {target}  ({'installed' if target.exists() else 'not installed'})")
    if not target.exists():
        return
    if _is_macos():
        r = _run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"])
        if r.returncode != 0:
            print("State: not loaded")
            return
        for line in r.stdout.splitlines():
            s = line.strip()
            if s.startswith(("state =", "pid =", "last exit code =")):
                print(f"  {s}")
    else:
        r = _run(["systemctl", "--user", "status", UNIT, "--no-pager"])
        print(r.stdout.strip() or r.stderr.strip())


def dispatch(action: str, home: str, host: str = "127.0.0.1", port: int = 8787,
             no_start: bool = False) -> None:
    if action == "install":
        install(home, host, port, start=not no_start)
    elif action == "uninstall":
        uninstall()
    elif action == "start":
        _service_start()
    elif action == "stop":
        _service_stop()
    elif action == "restart":
        _service_stop(quiet=True)
        _service_start()
    elif action == "status":
        status()
    else:
        raise ValueError(f"unknown action: {action}")
