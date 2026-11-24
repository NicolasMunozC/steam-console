"""The gamescope window that runs the desktop Steam in Big Picture.

Nothing is streamed and nothing is containerised: gamescope opens one window on
the desktop you are sitting at and runs *your* Steam inside it, so Big Picture
renders on a display Steam believes it owns — its display panel offers
resolution, refresh and framerate limit instead of hiding them — while the
libraries, `compatdata` prefixes, non-Steam shortcuts and controller layouts
stay the ones the desktop already uses.

Two rules come from using that Steam:

* one Steam at a time — Steam rewrites its config files whole, so the desktop
  client is closed and verified gone before gamescope starts;
* the display mode has to match the monitor (see :mod:`steam_console.display`).

A third is optional, and costs something: ``-e`` makes Steam believe it owns the
machine, so it offers SteamOS's power actions and hides "Exit Steam". Leaving
the console is then the power menu's "Switch to desktop", which runs a helper
named :data:`SESSION_SELECT` — a helper a desktop machine does not have. Steam
only calls it when it believes it is on a Deck (``-steamos3``), and in that mode
it also powers the Bluetooth radio off. So the helper comes with ``--steamos``:
the exit, at the price of the radio.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable

from .display import ConsoleError, DisplayMode, detect_display, resolve_display

#: The client a podstage streaming session shows (its ``PS_STEAM_FLAGS``):
#: Big Picture, gamepad-first, no desktop UI. ``-steamos3`` is *not* here: it is
#: what ``--steamos`` adds, because it makes Steam believe it is a Deck and power
#: the Bluetooth radio off.
STEAM_FLAGS = "-gamepadui"

#: How long a graceful ``steam -shutdown`` gets before gamescope opens anyway.
CLOSE_TIMEOUT_S = 45

#: What Steam runs for the power menu's "Switch to desktop".
SESSION_SELECT = "steamos-session-select"

_SESSION_SELECT_SCRIPT = """#!/bin/sh
# Written by steam-console for the length of one session.
# "Switch to desktop" is the exit Steam's power menu offers once gamescope's
# Steam integration is on, and this is the helper it runs to take it. There is
# no session to switch to: the desktop was underneath all along, so leaving the
# console means the client quits and gamescope follows it.
printf 'steam-console: leaving the console (%s)\\n' "${*:-desktop}" >&2
exec steam -shutdown
"""


def gamescope_argv(mode: DisplayMode, backend: str,
                   steam_flags: str = STEAM_FLAGS,
                   *, steamos: bool = False) -> list[str]:
    """The fullscreen gamescope that runs the desktop Steam in Big Picture.

    The tail of this list mirrors podstage's ``containers/runtime/runner.sh``
    (the gamescope line a streamed session uses) and should stay that way.

    ``-e`` (Steam integration) is load-bearing: it makes gamescope own the
    overlay — when Steam raises it, gamescope shows it above the game and hides
    the game window underneath, and closing it restores the game. Without it the
    overlay is just another window and lands *below* a fullscreen game.
    """
    flags = steam_flags.split()
    if steamos and "-steamos3" not in flags:   # the power menu's exit needs it,
        flags.insert(0, "-steamos3")           # and it costs the Bluetooth radio
    size = str(mode.width), str(mode.height)
    return [
        "gamescope", "--backend", backend,
        "-W", size[0], "-H", size[1],   # gamescope's output
        "-w", size[0], "-h", size[1],   # render target: equal, so no scaling
        "-r", str(mode.refresh),
        "-C", "3000",                  # hide the cursor, as the session does
        "--expose-wayland",
        "--force-windows-fullscreen",
        "-e",                          # Steam integration: the overlay is ours
        "-f", "--", "steam", *flags,
    ]


def default_backend() -> str:
    """gamescope's own backend: a client of the running session, never headless."""
    return "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11"


# --- the one-Steam rule ---------------------------------------------------

def _run(argv: list[str]) -> str:
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout or ""


def steam_running() -> bool:
    """True when a Steam is up on the host."""
    return bool(_run(["pgrep", "-af", "steamwebhelper"]).strip())


def close_steam(timeout: int = CLOSE_TIMEOUT_S) -> bool:
    """Gracefully quit the desktop Steam and wait for it. True once it is gone."""
    if not steam_running():
        return True
    print("Closing Steam (one Steam at a time)…")
    _run(["steam", "-shutdown"])
    for _ in range(timeout):
        if not steam_running():
            return True
        time.sleep(1)
    return False


# --- the way out ----------------------------------------------------------

def _exec_capable(directory: str) -> bool:
    """True when a script written here can be run — a ``noexec`` mount is not."""
    probe = pathlib.Path(directory, ".steam-console-probe")
    try:
        probe.write_text("#!/bin/sh\nexit 0\n")
        probe.chmod(0o755)
        return subprocess.run([str(probe)], check=False).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        probe.unlink(missing_ok=True)


def prepare_session_select() -> str | None:
    """A directory whose ``steamos-session-select`` Steam can actually run.

    Prepared before Steam is closed on purpose: a machine with no writable,
    executable temporary directory fails while the desktop client is open.
    """
    for base in (os.environ.get("XDG_RUNTIME_DIR"), tempfile.gettempdir()):
        if not base or not _exec_capable(base):
            continue
        try:
            directory = tempfile.mkdtemp(prefix="steam-console-", dir=base)
            script = pathlib.Path(directory, SESSION_SELECT)
            script.write_text(_SESSION_SELECT_SCRIPT)
            script.chmod(0o755)
        except OSError:
            continue
        return directory
    return None


def session_env(shim: str) -> dict[str, str]:
    """The environment the session runs in: the shim first on PATH."""
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([shim, env.get("PATH", "")])
    return env


# --- running it -----------------------------------------------------------

def launch(argv: list[str], env: dict[str, str] | None = None) -> int:
    """Run gamescope in the foreground until Steam exits."""
    return subprocess.run(argv, check=False, env=env).returncode


def run(*, resolution: str | None = None, steam_flags: str = STEAM_FLAGS,
        close_steam_first: bool = True, print_only: bool = False,
        steamos: bool = False,
        launch_fn: Callable[[list[str]], int] | None = None,
        detect: Callable[[], DisplayMode | None] | None = None) -> int:
    """Open the console session. Returns a process exit code.

    ``steamos`` trades the Bluetooth radio for the power menu's exit: it adds
    ``-steamos3``, without which Steam never calls the session-select helper.
    """
    for tool in ("gamescope", "steam"):
        if shutil.which(tool) is None:
            print(f"steam-console: {tool} is not installed", file=sys.stderr)
            return 1

    try:
        mode = resolve_display(resolution, detect=detect or detect_display)
    except ValueError as exc:
        print(f"steam-console: {exc}", file=sys.stderr)
        return 2
    except ConsoleError as exc:
        print(f"steam-console: {exc}", file=sys.stderr)
        return 1

    argv = gamescope_argv(mode, default_backend(), steam_flags, steamos=steamos)
    print(f"Steam Console on {mode}")
    if print_only:
        # A preview touches nothing and keeps stdout to one command line.
        print(" ".join(argv))
        if steamos:
            print(f"steam-console: also a temporary {SESSION_SELECT} on PATH, "
                  "so the power menu can leave", file=sys.stderr)
        return 0

    shim = None
    if steamos:
        shim = prepare_session_select()
        if shim is None:
            print("steam-console: no writable, executable directory for the "
                  "exit helper; point XDG_RUNTIME_DIR at one", file=sys.stderr)
            return 1

    if close_steam_first:
        if not close_steam():
            print("  (Steam still running — Big Picture may open in the "
                  "existing window instead)")
    elif steam_running():
        print("steam-console: a Steam is already running; close it, or drop "
              "--keep-steam so it is closed for you", file=sys.stderr)
        return 1

    if steamos:
        print("  exit: the power menu's “Switch to desktop”, or Ctrl+C here")
        print("  (SteamOS mode: Steam powers Bluetooth off in this session)")
    else:
        print("  exit: close Big Picture, or Ctrl+C here")
    try:
        # An injected launcher keeps its one-argument contract.
        if launch_fn is not None:
            return launch_fn(argv)
        return launch(argv, session_env(shim) if shim else None)
    except OSError as exc:
        print(f"steam-console: could not start gamescope: {exc}",
              file=sys.stderr)
        return 1
    finally:
        if shim:
            shutil.rmtree(shim, ignore_errors=True)
