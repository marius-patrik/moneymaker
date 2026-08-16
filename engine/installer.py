"""Strategy install and upgrade: copy bundled strategies to home dir with hash tracking."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Optional


MANIFEST_FILE = ".strategy_manifest.json"
VERSION_FILE = ".version"


def _bundled_dir() -> pathlib.Path:
    """Bundled strategies are in strategies/ at the repo root, sibling of the engine/ package."""
    return pathlib.Path(__file__).parent.parent / "strategies"


def _file_sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(home: str) -> dict:
    path = os.path.join(home, MANIFEST_FILE)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _write_manifest(home: str, manifest: dict) -> None:
    path = os.path.join(home, MANIFEST_FILE)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def install_strategies(home: str, force: bool = False) -> dict[str, list[str]]:
    """
    Copy bundled strategies from strategies/ to <home>/strategies/.

    Rules per file:
      - Not in home yet                 → install always
      - In home, not in manifest        → conflict (user-added file, skip unless force)
      - In home, hash == manifest hash  → user unmodified; update to latest bundled version
      - In home, hash != manifest hash  → user modified; skip unless force

    Returns a dict with keys: installed, updated, unchanged, conflicts.
    """
    bundled = _bundled_dir()
    if not bundled.is_dir():
        raise FileNotFoundError(f"Bundled strategies dir not found: {bundled}")

    home_strat = pathlib.Path(home) / "strategies"
    home_strat.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(home)
    new_manifest = dict(manifest)

    result: dict[str, list[str]] = {
        "installed": [], "updated": [], "unchanged": [], "conflicts": []
    }

    for src in sorted(bundled.glob("*.py")):
        if src.name.startswith("_"):
            continue
        dest = home_strat / src.name
        bundled_hash = _file_sha256(src)

        if not dest.exists():
            shutil.copy2(src, dest)
            new_manifest[src.name] = bundled_hash
            result["installed"].append(src.name)
            continue

        current_hash = _file_sha256(dest)
        installed_hash = manifest.get(src.name)

        if force:
            shutil.copy2(src, dest)
            new_manifest[src.name] = bundled_hash
            if current_hash != bundled_hash:
                result["updated"].append(src.name)
            else:
                result["unchanged"].append(src.name)
        elif installed_hash is None or current_hash != installed_hash:
            # Untracked file or user-modified → conflict
            result["conflicts"].append(src.name)
        elif current_hash == bundled_hash:
            # Unmodified and already at latest version
            new_manifest[src.name] = bundled_hash
            result["unchanged"].append(src.name)
        else:
            # Unmodified but bundled has a newer version → update
            shutil.copy2(src, dest)
            new_manifest[src.name] = bundled_hash
            result["updated"].append(src.name)

    _write_manifest(home, new_manifest)
    return result


def print_install_result(result: dict[str, list[str]]) -> None:
    if result.get("installed"):
        print(f"Installed:  {', '.join(result['installed'])}")
    if result.get("updated"):
        print(f"Updated:    {', '.join(result['updated'])}")
    if result.get("unchanged"):
        print(f"Unchanged:  {', '.join(result['unchanged'])}")
    if result.get("conflicts"):
        print("\nConflicts (locally modified — skipped):")
        for name in result["conflicts"]:
            print(f"  {name}")
        print("  Use `upgrade-strategies --force` to overwrite, or edit manually.")
    if not any(result.values()):
        print("Nothing to do.")


def run_upgrade(home: str) -> None:
    """Pull the latest version from the repo, reinstall, then sync strategies."""
    repo_root = pathlib.Path(__file__).parent.parent
    print(f"Pulling latest code from {repo_root} ...")
    result = subprocess.run(["git", "pull"], cwd=repo_root)
    if result.returncode != 0:
        print("git pull failed. Fix the issue above and retry.", file=sys.stderr)
        sys.exit(1)
    print("Re-installing package ...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(repo_root), "-q"],
        check=True,
    )
    print("Syncing strategies ...")
    r = install_strategies(home, force=False)
    print_install_result(r)


def check_version(home: str) -> None:
    """Write current version to home dir; warn if it changed since last run."""
    from engine import __version__
    version_path = os.path.join(home, VERSION_FILE)
    if os.path.exists(version_path):
        with open(version_path) as f:
            stored = f.read().strip()
        if stored and stored != __version__:
            print(
                f"moneymaker updated {stored} → {__version__}. "
                "Run `moneymaker upgrade-strategies` to sync bundled strategies.",
                file=sys.stderr,
            )
    with open(version_path, "w") as f:
        f.write(__version__)
