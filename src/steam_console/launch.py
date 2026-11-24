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
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable

from .display import ConsoleError, DisplayMode, detect_display, resolve_display

#: The same client a podstage streaming session shows (its ``PS_STEAM_FLAGS``):
#: Big Picture, gamepad-first, no desktop UI.
STEAM_FLAGS = "-gamepadui"

#: How long a graceful ``steam -shutdown`` gets before gamescope opens anyway.
CLOSE_TIMEOUT_S = 20


def gamescope_argv(mode: DisplayMode, backend: str,
                   steam_flags: str = STEAM_FLAGS) -> list[str]:
    """The fullscreen gamescope that runs the desktop Steam in Big Picture.

    The tail of this list mirrors podstage's ``containers/runtime/runner.sh``
    (the gamescope line a streamed session uses) and should stay that way.

    ``-e`` (Steam integration) is load-bearing: it makes gamescope own the
    overlay — when Steam raises it, gamescope shows it above the game and hides
    the game window underneath, and closing it restores the game. Without it the
    overlay is just another window and lands *below* a fullscreen game.
    """
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
        "-f", "--", "steam", *steam_flags.split(),
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


# --- running it -----------------------------------------------------------

def launch(argv: list[str]) -> int:
    """Run gamescope in the foreground until Steam exits."""
    return subprocess.run(argv, check=False).returncode


def run(*, resolution: str | None = None, steam_flags: str = STEAM_FLAGS,
        close_steam_first: bool = True, print_only: bool = False,
        launch_fn: Callable[[list[str]], int] | None = None,
        detect: Callable[[], DisplayMode | None] | None = None) -> int:
    """Open the console session. Returns a process exit code."""
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

    argv = gamescope_argv(mode, default_backend(), steam_flags)
    print(f"Steam Console on {mode}")
    if print_only:
        # A preview must not disturb the client it is describing.
        print(" ".join(argv))
        return 0

    if close_steam_first:
        if not close_steam():
            print("  (Steam still running — Big Picture may open in the "
                  "existing window instead)")
    elif steam_running():
        print("steam-console: a Steam is already running; close it, or drop "
              "--keep-steam so it is closed for you", file=sys.stderr)
        return 1

    print("  exit: close Big Picture, or Ctrl+C here")
    try:
        return (launch_fn or launch)(argv)
    except OSError as exc:
        print(f"steam-console: could not start gamescope: {exc}",
              file=sys.stderr)
        return 1
