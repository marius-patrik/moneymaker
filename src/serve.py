"""Single-command dev/prod runner: API + web UI under one process tree.

`moneymaker serve` starts the FastAPI backend and, in dev mode, the RSBuild
dev server alongside it, streaming both logs with prefixes and shutting both
down together on Ctrl+C.

Two modes:
  dev  (default) — uvicorn --reload on :8787, bun dev on :5173 proxying /api.
                   Two ports; hot reload on both sides.
  prod (--prod)  — builds ui/dist, then serves API *and* UI from :8787.
                   One port, no bun process, no reload.

Designed to be the single entry point a service manager (systemd/launchd)
supervises: it runs in the foreground, logs to stdout, and exits non-zero if
a child dies unexpectedly.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import threading
from typing import Optional

_REPO_ROOT = pathlib.Path(__file__).parent.parent
_UI_DIR = _REPO_ROOT / "ui"

# ANSI colours for log prefixes; disabled when not a tty.
_COLOURS = {"api": "\033[36m", "ui": "\033[35m", "reset": "\033[0m"}


def _prefix(name: str) -> str:
    if not sys.stdout.isatty():
        return f"[{name}] "
    colour = _COLOURS.get(name, "")
    return f"{colour}[{name}]{_COLOURS['reset']} "


def _pump(stream, name: str) -> None:
    """Forward a child's output to our stdout, line by line, with a prefix."""
    pre = _prefix(name)
    try:
        for raw in iter(stream.readline, b""):
            sys.stdout.write(pre + raw.decode(errors="replace"))
            sys.stdout.flush()
    except (ValueError, OSError):
        pass  # stream closed during shutdown


def _spawn(cmd: list[str], cwd: pathlib.Path, name: str,
           env: Optional[dict] = None) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={**os.environ, **(env or {})},
        # Own process group so we can signal the whole tree.
        start_new_session=True,
    )
    threading.Thread(target=_pump, args=(proc.stdout, name), daemon=True).start()
    return proc


def _port_in_use(host: str, port: int) -> bool:
    """Check before spawning, so a collision is one clear error not a restart loop."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _ui_deps_installed() -> bool:
    return (_UI_DIR / "node_modules").is_dir()


def _build_ui() -> None:
    print(_prefix("ui") + "building production bundle…")
    subprocess.run(["bun", "run", "build"], cwd=str(_UI_DIR), check=True)


def serve(home: str, host: str = "127.0.0.1", port: int = 8787,
          ui_port: int = 5173, prod: bool = False, no_ui: bool = False) -> int:
    """Run the API (and UI) in the foreground. Returns a process exit code."""
    if _port_in_use(host, port):
        print(f"error: {host}:{port} is already in use — another server is running.\n"
              f"       Stop it, or pass --port to use a different one.", file=sys.stderr)
        return 3

    bun = shutil.which("bun")
    want_ui = not no_ui

    if want_ui and not bun:
        print("warning: bun not found on PATH — starting API only.\n"
              "         install bun (https://bun.sh) to run the web UI.",
              file=sys.stderr)
        want_ui = False

    if want_ui and not _ui_deps_installed():
        print(_prefix("ui") + "installing dependencies (first run)…")
        subprocess.run(["bun", "install"], cwd=str(_UI_DIR), check=True)

    procs: dict[str, subprocess.Popen] = {}

    # In prod we build the UI first; FastAPI then serves ui/dist itself, so
    # there is no second process and everything lives on one port.
    if want_ui and prod:
        _build_ui()

    api_cmd = [sys.executable, "-m", "uvicorn", "src.server:create_app",
               "--factory", "--host", host, "--port", str(port)]
    if not prod:
        api_cmd += ["--reload", "--reload-dir", str(_REPO_ROOT / "src")]

    procs["api"] = _spawn(api_cmd, _REPO_ROOT, "api", env={"MONEYMAKER_HOME": home})

    if want_ui and not prod:
        procs["ui"] = _spawn(
            ["bun", "run", "dev"], _UI_DIR, "ui",
            # rsbuild.config.ts reads both of these (see source.entry there).
            env={"MONEYMAKER_API": f"http://{host}:{port}",
                 "MONEYMAKER_UI_PORT": str(ui_port)},
        )

    ui_url = f"http://localhost:{ui_port}" if (want_ui and not prod) else f"http://{host}:{port}"
    print()
    print(f"  Web UI   {ui_url}")
    print(f"  API      http://{host}:{port}/api/")
    print(f"  Docs     http://{host}:{port}/docs")
    print(f"  Data     {home}")
    print(f"  Mode     {'production' if prod else 'development (hot reload)'}")
    print("\n  Ctrl+C to stop.\n")

    stopping = threading.Event()

    def _shutdown(signum=None, frame=None):
        if stopping.is_set():
            return
        stopping.set()
        print("\nshutting down…")
        for proc in procs.values():
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    proc.terminate()
        for proc in procs.values():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    proc.kill()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Supervise: if any child exits, bring the whole thing down. A service
    # manager sees the non-zero code and restarts us.
    exit_code = 0
    tick = threading.Event()
    try:
        while not stopping.is_set():
            dead = [(n, p.poll()) for n, p in procs.items() if p.poll() is not None]
            if dead:
                name, code = dead[0]
                print(f"\n{name} exited with code {code}", file=sys.stderr)
                exit_code = code or 1
                _shutdown()
                break
            tick.wait(0.3)
    except KeyboardInterrupt:
        _shutdown()

    return exit_code
