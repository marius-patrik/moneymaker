"""
Tests for service-manager integration (src/service.py).

These exercise template rendering and path selection for both platforms.
Nothing here installs, loads, or starts a real service — the launchctl and
systemctl calls are never reached.

CI runs on Linux, so the systemd path here is genuinely exercised on the
platform it targets, which local development on macOS cannot do.
"""

import pathlib
from unittest import mock

import pytest

import src.service as svc


@pytest.fixture
def home(tmp_path):
    return str(tmp_path / "data")


def _render(template_name: str, home: str) -> str:
    return svc._render(svc._DEPLOY / template_name, home, "127.0.0.1", 8787)


# ---------------------------------------------------------------- templates

def test_both_templates_ship_with_the_repo():
    assert (svc._DEPLOY / f"{svc.LABEL}.plist").is_file()
    assert (svc._DEPLOY / svc.UNIT).is_file()


@pytest.mark.parametrize("template", ["com.moneymaker.server.plist", "moneymaker.service"])
def test_render_leaves_no_placeholders(template, home):
    out = _render(template, home)
    assert "__" not in out, f"unsubstituted placeholder in {template}:\n{out}"


@pytest.mark.parametrize("template", ["com.moneymaker.server.plist", "moneymaker.service"])
def test_render_uses_absolute_paths_and_prod_mode(template, home):
    out = _render(template, home)
    assert home in out                      # data dir threaded through
    assert str(svc._REPO_ROOT) in out       # working directory
    assert "serve" in out and "--prod" in out
    assert "8787" in out


def test_systemd_unit_quotes_environment_values(home):
    """
    systemd treats an unquoted space as a separator between assignments, and
    PATH routinely contains spaces (e.g. "Application Support"). Unquoted
    Environment= lines silently truncate PATH on Linux.
    """
    out = _render(svc.UNIT, home)
    env_lines = [l for l in out.splitlines() if l.startswith("Environment=")]
    assert env_lines, "unit declares no Environment lines"
    for line in env_lines:
        value = line.split("=", 1)[1]
        assert value.startswith('"') and value.endswith('"'), (
            f"unquoted Environment value would break on spaces: {line}"
        )


def test_systemd_unit_restarts_on_failure(home):
    out = _render(svc.UNIT, home)
    assert "Restart=always" in out


def test_launchd_plist_is_valid_xml_and_keeps_alive(home):
    """The plist must parse — launchd rejects malformed XML outright."""
    import plistlib

    out = _render(f"{svc.LABEL}.plist", home)
    parsed = plistlib.loads(out.encode())

    assert parsed["Label"] == svc.LABEL
    assert parsed["RunAtLoad"] is True
    # Restart on failure, but not after a clean stop.
    assert parsed["KeepAlive"] == {"SuccessfulExit": False}
    assert "--prod" in parsed["ProgramArguments"]


# -------------------------------------------------------------------- paths

def test_target_path_follows_the_platform():
    with mock.patch.object(svc, "_is_macos", return_value=True):
        assert svc._target_path() == svc._plist_path()
        assert "LaunchAgents" in str(svc._target_path())

    with mock.patch.object(svc, "_is_macos", return_value=False):
        assert svc._target_path() == svc._unit_path()
        assert "systemd/user" in str(svc._target_path())


def test_log_dir_is_created_under_home(home):
    d = svc._log_dir(home)
    assert d == pathlib.Path(home) / "logs"
    assert d.is_dir()


def test_log_dir_tolerates_an_unreachable_path():
    """
    Rendering a unit must not fail because the data dir isn't reachable from
    the machine doing the render — the path may only exist on the target.
    """
    d = svc._log_dir("/proc/nonexistent-does-not-exist/data")
    assert d.name == "logs"          # returns the path regardless
    assert not d.exists()


def test_dispatch_rejects_unknown_actions(home):
    with pytest.raises(ValueError, match="unknown action"):
        svc.dispatch("frobnicate", home)
