"""The gamescope command, the one-Steam rule, and the exit codes."""

import os
from pathlib import Path

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


def test_steamos_mode_is_opt_in_and_adds_the_deck_flag():
    """-steamos3 is the power menu's exit and also what makes Steam power the
    Bluetooth radio off, so it only comes when asked for."""
    plain = launch.gamescope_argv(MODE, "wayland")
    deck = launch.gamescope_argv(MODE, "wayland", steamos=True)

    assert plain[-2:] == ["steam", "-gamepadui"]
    assert deck[-3:] == ["steam", "-steamos3", "-gamepadui"]


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
    # Asked for SteamOS mode, custom flags get it too, or the exit would hang.
    deck = launch.gamescope_argv(MODE, "x11", "-gamepadui -noreactlogin",
                                 steamos=True)
    assert deck[-4:] == ["steam", "-steamos3", "-gamepadui", "-noreactlogin"]


@pytest.mark.parametrize("wayland,expected", [(None, "x11"), ("wayland-1", "wayland")])
def test_backend_follows_the_session_type(monkeypatch, wayland, expected):
    if wayland is None:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    else:
        monkeypatch.setenv("WAYLAND_DISPLAY", wayland)

    assert launch.default_backend() == expected


def shim_on(path):
    """The session-select helper ``path`` points Steam at, if there is one."""
    for directory in path.split(os.pathsep):
        candidate = Path(directory, launch.SESSION_SELECT)
        if candidate.is_file():
            return candidate
    return None


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
    monkeypatch.setattr(launch, "launch", lambda argv, env=None: 0)

    assert launch.run(resolution="big") == 2
    assert "WxH@R" in capsys.readouterr().err


def test_closes_steam_before_opening_gamescope(monkeypatch):
    order = []
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: order.append("close") or True)
    monkeypatch.setattr(launch, "launch",
                        lambda argv, env=None: order.append("launch") or 0)

    assert launch.run() == 0
    assert order == ["close", "launch"]


def test_launches_anyway_when_the_close_times_out(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: False)
    launched = []
    monkeypatch.setattr(launch, "launch",
                        lambda argv, env=None: launched.append(argv) or 0)

    assert launch.run() == 0
    assert launched
    assert "still running" in capsys.readouterr().out


def test_keep_steam_skips_the_shutdown(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "steam_running", lambda: False)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: pytest.fail("must not close"))
    monkeypatch.setattr(launch, "launch", lambda argv, env=None: 0)

    assert launch.run(close_steam_first=False) == 0


def test_a_running_steam_blocks_a_launch_that_must_not_touch_it(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "steam_running", lambda: True)
    launched = []
    monkeypatch.setattr(launch, "launch",
                        lambda argv, env=None: launched.append(argv) or 0)

    assert launch.run(close_steam_first=False) == 1
    assert launched == []
    assert "Steam" in capsys.readouterr().err


def test_print_only_shows_the_command_and_touches_nothing(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: pytest.fail("a preview must not close Steam"))
    monkeypatch.setattr(launch, "launch",
                        lambda argv, env=None: pytest.fail("must not launch"))

    assert launch.run(print_only=True) == 0
    out, err = capsys.readouterr()
    # stdout stays one command line: a wrapper may read it as the command.
    assert out.splitlines()[-1].startswith("gamescope") and "-W 1920" in out
    # Nothing about a helper nobody will get: SteamOS mode is off by default.
    assert launch.SESSION_SELECT not in err


def test_the_preview_mentions_the_helper_in_steamos_mode(monkeypatch, capsys):
    prepare(monkeypatch)

    assert launch.run(print_only=True, steamos=True) == 0
    assert launch.SESSION_SELECT in capsys.readouterr().err


def test_the_default_session_needs_no_temporary_directory(monkeypatch):
    """Without --steamos there is no helper to prepare, so a machine with an
    unwritable or noexec temporary directory still gets its console."""
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "prepare_session_select",
                        lambda: pytest.fail("no helper is needed by default"))
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)
    seen = []
    monkeypatch.setattr(launch, "launch",
                        lambda argv, env=None: seen.append(env) or 0)

    assert launch.run() == 0
    assert seen == [None]


def test_a_failing_helper_is_reported_before_steam_is_closed(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "_exec_capable", lambda directory: False)
    monkeypatch.setattr(launch, "close_steam",
                        lambda timeout=20: pytest.fail("must stay open"))

    assert launch.run(steamos=True) == 1
    assert "exit helper" in capsys.readouterr().err


def test_an_injected_launcher_keeps_its_one_argument_contract(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)
    seen = []

    assert launch.run(launch_fn=lambda argv: seen.append(argv) or 0) == 0
    assert seen and seen[0][0] == "gamescope"


def test_launch_failure_is_reported_not_raised(monkeypatch, capsys):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)

    def boom(argv, env=None):
        raise OSError("no such file")

    monkeypatch.setattr(launch, "launch", boom)

    assert launch.run() == 1
    assert "no such file" in capsys.readouterr().err


def test_the_power_menu_can_leave_the_console(monkeypatch):
    """-e hands Steam the SteamOS power menu, which has no "Exit Steam": its
    "Switch to desktop" runs steamos-session-select. Without that helper on
    PATH the dialog waits forever for a session that does not exist here."""
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)
    found = {}

    def look(argv, env=None):
        found["shim"] = shim_on(env["PATH"])
        found["path"] = env["PATH"]
        if found["shim"]:
            found["script"] = found["shim"].read_text()
            found["runs"] = os.access(found["shim"], os.X_OK)
        return 0

    monkeypatch.setattr(launch, "launch", look)

    assert launch.run(steamos=True) == 0
    assert found["runs"] is True
    assert "exec steam -shutdown" in found["script"]
    # Prepended, not replaced: Steam still needs the machine's own PATH.
    assert found["path"].split(os.pathsep)[1:] == \
        os.environ["PATH"].split(os.pathsep)


def test_the_helper_does_not_outlive_the_session(monkeypatch):
    prepare(monkeypatch)
    monkeypatch.setattr(launch, "close_steam", lambda timeout=20: True)
    seen = {}

    def remember(argv, env=None):
        seen["path"] = env["PATH"]
        return 0

    monkeypatch.setattr(launch, "launch", remember)

    assert launch.run(steamos=True) == 0

    assert not Path(seen["path"].split(os.pathsep)[0]).exists()


def test_steam_is_detected_by_its_helper_process(monkeypatch):
    monkeypatch.setattr(launch, "_run", lambda argv: "4242 steamwebhelper\n")

    assert launch.steam_running() is True


def test_no_helper_process_means_no_steam(monkeypatch):
    monkeypatch.setattr(launch, "_run", lambda argv: "")

    assert launch.steam_running() is False
