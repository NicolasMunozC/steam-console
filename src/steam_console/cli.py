"""Command line: one verb, because this tool does one thing."""

from __future__ import annotations

import argparse
import sys

from . import __version__, launch
from .launch import STEAM_FLAGS

DESCRIPTION = ("run the desktop Steam in Big Picture under a fullscreen "
               "gamescope, on this machine, like a real console")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="steam-console", description=DESCRIPTION)
    p.add_argument("-V", "--version", action="version",
                   version=f"steam-console {__version__}")
    p.add_argument("--resolution", metavar="WxH@R",
                   help="gamescope output size (default: the focused "
                        "monitor's current mode)")
    p.add_argument("--steam-flags", default=STEAM_FLAGS, metavar="FLAGS",
                   help=f"Steam launch flags (default: {STEAM_FLAGS})")
    p.add_argument("--keep-steam", action="store_true",
                   help="do not close Steam first (it must not be running)")
    p.add_argument("--print-only", action="store_true",
                   help="print the gamescope command instead of running it")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return launch.run(resolution=args.resolution,
                          steam_flags=args.steam_flags,
                          close_steam_first=not args.keep_steam,
                          print_only=args.print_only)
    except KeyboardInterrupt:
        print("\nsteam-console: interrupted", file=sys.stderr)
        return 130
