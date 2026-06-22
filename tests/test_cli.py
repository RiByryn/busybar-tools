"""Argparse-level tests: only argument parsing/validation (no dispatch to device)."""
import sys

import pytest

from busybar_tools.cli import busybar_main


def run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["busybar"] + argv)
    return busybar_main()


@pytest.mark.parametrize("cmd", ["install", "fetch", "write-recovery"])
def test_source_is_required(monkeypatch, cmd):
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, [cmd])
    assert exc.value.code == 2


def test_auto_install_rejects_firmware_flags(monkeypatch):
    # autodetect-only: no -t override allowed
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["auto-install", "-t", "22", "dev"])


def test_install_signed_and_unsigned_are_mutually_exclusive(monkeypatch):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["install", "--signed", "--unsigned", "dev"])


def test_install_via_http_with_no_invoke_update_errors(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, ["install", "--via-http", "--no-invoke-update", "dev"])
    assert exc.value.code == 2


def test_help_exits_zero_and_mentions_auto_install(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, ["--help"])
    assert exc.value.code == 0
    assert "auto-install" in capsys.readouterr().out


def test_command_registration_order(monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, ["--help"])
    out = capsys.readouterr().out
    assert "{auto-install,install,write-recovery,fetch,install-onboard,cli,wait,clean,storage}" in out
