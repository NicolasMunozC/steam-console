"""The gamescope command, the one-Steam rule, and the exit codes."""

import pytest

from steam_console import launch

MODE = launch.DisplayMode(3440, 1440, 180, "DP-3")
SMALL = launch.DisplayMode(1920, 1080, 60)


def nowhere(_name):
    return None


def installed(name):
    return "/usr/bin/" + name


def test_gamescope_matches_the_monitor_mode_on_both_sides():
    argv = launch.gamescope_argv(MODE, "wayland")

    # -W/-H size gamescope's output, -w/-h the render target: equal sizes mean
    # no scaling between them, so Steam's display panel tells the truth.
    assert argv == [
        "gamescope", "--backend", "wayland",
        "-W", "3440", "-H", "1440", "-w", "3440", "-h", "1440",
        "-r", "180", "-C", "3000", "--expose-wayland",
        "--force-windows-fullscreen", "-e",
        "-f", "--", "steam", "-gamepadui",
    ]


def test_gamescope_keeps_the_session_stack_flags():
    """-e is the one that matters for the overlay: gamescope owns it, shows it
    above the game and hides the game under it, where a plain nested gamescope
    leaves the overlay behind a fullscreen app."""
    argv = launch.gamescope_argv(launch.DisplayMode(1920, 1080, 60), "wayland")

    assert "-e" in argv
    assert "--force-windows-fullscreen" in argv
    assert "--expose-wayland" in argv
    assert argv[argv.index("-C") + 1] == "3000"


def test_steam_runs_in_big_picture_like_the_streamed_session():
    argv = launch.gamescope_argv(MODE, "x11", "-gamepadui -noreactlogin")

    assert argv[-3:] == ["steam", "-gamepadui", "-noreactlogin"]
    assert launch.STEAM_FLAGS == "-gamepadui"


@pytest.mark.parametrize("wayland,expected", [(None, "x11"), ("wayland-1", "wayland")])
def test_backend_follows_the_session_type(monkeypatch, wayland, expected):
    if wayland is None:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    else:
        monkeypatch.setenv("WAYLAND_DISPLAY", wayland)

    assert launch.default_backend() == expected


def prepare(monkeypatch, mode=None):
    """Every prerequisite satisfied; the test decides what to watch."""
    monkeypatch.setattr(launch.shutil, "which", installed)
    monkeypatch.setattr(launch, "detect_display", lambda: mode or SMALL)


def test_refuses_to_launch_without_a_display_mode(monkeypatch, capsys):
    monkeypatch.setattr(launch.shutil, "which", installed)
    monkeypatch.setattr(launch, "detect_display", lambda: None)
    launched = []
    monkeypatch.setattr(launch, "launch", lambda argv: launched.append(argv) or 0)

    assert launch.run() == 1
    assert launched == []
    assert "--resolution" in capsys.readouterr().err


def test_refuses_to_launch_without_gamescope(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch.shutil, "which", nowhere)
    launched = []
    monkeypatch.setattr(launch, "launch", lambda argv: launched.append(argv) or 0)

    assert launch.run() == 1
    assert launched == []
    assert "gamescope" in capsys.readouterr().err


def test_a_bad_resolution_is_a_usage_error(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)
    monkeypatch.setattr(launch, "launch", lambda argv: 0)

    assert launch.run(resolution="big") == 2
    assert "WxH@R" in capsys.readouterr().err


def test_closes_steam_before_opening_gamescope(monkeypatch):
    order = []
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: order.append("close") or True)
    monkeypatch.setattr(launch, "launch",
                        lambda argv: order.append("launch") or 0)

    assert launch.run() == 0
    assert order == ["close", "launch"]


def test_launches_anyway_when_the_close_times_out(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: False)
    launched = []
    monkeypatch.setattr(launch, "launch", lambda argv: launched.append(argv) or 0)

    assert launch.run() == 0
    assert launched
    assert "still running" in capsys.readouterr().out


def test_keep_steam_skips_the_shutdown(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "steam_running", lambda: False)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: pytest.fail("must not close"))
    monkeypatch.setattr(launch, "launch", lambda argv: 0)

    assert launch.run(close_steam_first=False) == 0


def test_a_running_steam_blocks_a_launch_that_must_not_touch_it(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "steam_running", lambda: True)
    launched = []
    monkeypatch.setattr(launch, "launch", lambda argv: launched.append(argv) or 0)

    assert launch.run(close_steam_first=False) == 1
    assert launched == []
    assert "Steam" in capsys.readouterr().err


def test_print_only_shows_the_command_and_touches_nothing(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: pytest.fail("a preview must not close Steam"))
    monkeypatch.setattr(launch, "launch",
                        lambda argv: pytest.fail("must not launch"))

    assert launch.run(print_only=True) == 0
    out = capsys.readouterr().out
    assert "gamescope" in out and "-W 1920" in out


def test_launch_failure_is_reported_not_raised(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)

    def boom(argv):
        raise OSError("no such file")

    monkeypatch.setattr(launch, "launch", boom)

    assert launch.run() == 1
    assert "no such file" in capsys.readouterr().err


def test_steam_is_detected_by_its_helper_process(monkeypatch):
    monkeypatch.setattr(launch, "_run", lambda argv: "4242 steamwebhelper\n")

    assert launch.steam_running() is True


def test_no_helper_process_means_no_steam(monkeypatch):
    monkeypatch.setattr(launch, "_run", lambda argv: "")

    assert launch.steam_running() is False
