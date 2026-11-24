"""The command line: defaults, delegation, and the interrupt path."""

import pytest

from steam_console import cli


def test_defaults_mean_the_monitor_and_big_picture():
    args = cli.build_parser().parse_args([])

    # No --resolution: read the monitor. No --steam-flags: Big Picture.
    assert args.resolution is None
    assert args.steam_flags == "-gamepadui"
    assert args.steamos is False
    assert args.keep_steam is False
    assert args.print_only is False


def test_flags_reach_the_launcher_as_keywords(monkeypatch):
    seen = {}
    monkeypatch.setattr(cli.launch, "run", lambda **kwargs: seen.update(kwargs) or 0)

    assert cli.main(["--resolution", "1920x1080@60", "--keep-steam",
                     "--print-only", "--steamos"]) == 0
    assert seen == {
        "resolution": "1920x1080@60",
        "steam_flags": "-gamepadui",
        "close_steam_first": False,
        "print_only": True,
        "steamos": True,
    }


def test_the_exit_code_is_the_launcher_result(monkeypatch):
    monkeypatch.setattr(cli.launch, "run", lambda **kwargs: 1)

    assert cli.main([]) == 1


def test_interrupt_is_a_clean_exit(monkeypatch, capsys):
    def interrupted(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.launch, "run", interrupted)

    assert cli.main([]) == 130
    assert "interrupted" in capsys.readouterr().err


def test_version_is_printed():
    with pytest.raises(SystemExit) as done:
        cli.build_parser().parse_args(["--version"])

    assert done.value.code == 0


def test_unknown_flags_are_a_usage_error():
    with pytest.raises(SystemExit) as done:
        cli.build_parser().parse_args(["--chocolate"])

    assert done.value.code == 2
