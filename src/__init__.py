"""moneymaker — provider-agnostic paper/live trading engine."""

import pathlib
import re


def _version() -> str:
    """
    Report the version this checkout actually is.

    pyproject.toml wins when it is present. Installed distribution metadata
    is snapshotted at install time, so an editable install keeps reporting
    whatever it was installed as — and since every push auto-bumps the
    version, that goes stale immediately. Falling back to metadata keeps
    real (non-editable) installs correct, where there is no pyproject.toml
    alongside the package.
    """
    pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
    try:
        if pyproject.is_file():
            m = re.search(r'^version\s*=\s*"([^"]+)"',
                          pyproject.read_text(), re.MULTILINE)
            if m:
                return m.group(1)
    except OSError:
        pass

    try:
        from importlib.metadata import PackageNotFoundError, version
        return version("moneymaker")
    except Exception:
        return "0.0.0+dev"


__version__ = _version()
