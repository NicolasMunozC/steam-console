"""Which monitor mode to open at.

gamescope has to be opened at the monitor's own mode. Opening it at another
size means rendering at one resolution and scaling to another, which is exactly
the lie the display panel then tells: Steam reports gamescope's output, and the
eye sees the monitor's.

A guessed default would be that same lie, so the read failure is fatal and the
user passes ``--resolution`` instead.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

_XR_HEADER = re.compile(r"^(\S+)\s+connected\s*(.*)$")
_XR_MODE = re.compile(r"^\s+(\d+)x(\d+)\s+(.+)$")
_SPEC = re.compile(r"(\d+)x(\d+)(?:@(\d+(?:\.\d+)?))?")

#: The same names a podstage session accepts, so a resolution is spoken the
#: same way in both.
PRESETS = {
    "deck": (1280, 800, 60),
    "1080p60": (1920, 1080, 60),
    "1080p120": (1920, 1080, 120),
    "1440p60": (2560, 1440, 60),
    "4k60": (3840, 2160, 60),
}


class ConsoleError(RuntimeError):
    """The console session cannot be composed without guessing."""


@dataclass(frozen=True)
class DisplayMode:
    """One monitor mode: what gamescope has to be opened at."""

    width: int
    height: int
    refresh: int = 60
    output: str = ""

    def __str__(self) -> str:
        label = f"{self.width}x{self.height}@{self.refresh}"
        return f"{label} ({self.output})" if self.output else label


def _run(argv: list[str]) -> str:
    """stdout of ``argv``, or "" when the tool is missing or fails.

    Probes are tried in order on every host, so a missing binary is the normal
    case, not an error.
    """
    try:
        done = subprocess.run(argv, capture_output=True, text=True,
                              check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout or ""


def _focused_hyprland() -> DisplayMode | None:
    try:
        monitors = json.loads(_run(["hyprctl", "monitors", "-j"]) or "null")
    except json.JSONDecodeError:
        return None
    if not isinstance(monitors, list) or not monitors:
        return None
    monitor = next((m for m in monitors if m.get("focused")), monitors[0])
    try:
        return DisplayMode(int(monitor["width"]), int(monitor["height"]),
                           round(float(monitor.get("refreshRate", 60))),
                           str(monitor.get("name", "")))
    except (KeyError, TypeError, ValueError):
        return None


def _focused_sway() -> DisplayMode | None:
    try:
        outputs = json.loads(_run(["swaymsg", "-t", "get_outputs", "--raw"])
                             or "null")
    except json.JSONDecodeError:
        return None
    if not isinstance(outputs, list) or not outputs:
        return None
    output = next((o for o in outputs if o.get("focused")), outputs[0])
    mode = output.get("current_mode") or {}
    try:
        return DisplayMode(int(mode["width"]), int(mode["height"]),
                           round(int(mode.get("refresh", 60000)) / 1000),
                           str(output.get("name", "")))
    except (KeyError, TypeError, ValueError):
        return None


def _primary_xrandr() -> DisplayMode | None:
    text = _run(["xrandr", "--current"])
    if not text:
        return None
    current, primary, found = "", False, []
    for line in text.splitlines():
        header = _XR_HEADER.match(line)
        if header:
            current, primary = header.group(1), "primary" in header.group(2)
            continue
        mode = _XR_MODE.match(line)
        if not (mode and current):
            continue
        for token in mode.group(3).split():
            if "*" in token:   # the current rate: * alone, or *+ if preferred
                try:
                    refresh = round(float(token.rstrip("*+")))
                except ValueError:
                    refresh = 60
                found.append((primary,
                              DisplayMode(int(mode.group(1)), int(mode.group(2)),
                                          refresh, current)))
                break
    if not found:
        return None
    return next((mode for is_primary, mode in found if is_primary), found[0][1])


_PROBES = (_focused_hyprland, _focused_sway, _primary_xrandr)


def detect_display() -> DisplayMode | None:
    """The focused monitor's current mode, or None when no probe can tell."""
    for probe in _PROBES:
        mode = probe()
        if mode is not None:
            return mode
    return None


def parse_spec(spec: str) -> DisplayMode:
    """``WxH@R`` / ``WxH`` / a preset name from :data:`PRESETS`."""
    key = spec.strip().lower()
    if key in PRESETS:
        return DisplayMode(*PRESETS[key])
    match = _SPEC.fullmatch(key)
    if match is None:
        raise ValueError(
            f"not a resolution: {spec!r} (use WxH@R or one of "
            f"{', '.join(PRESETS)})")
    return DisplayMode(int(match.group(1)), int(match.group(2)),
                       round(float(match.group(3) or 60)))


def resolve_display(spec: str | None, *, detect=None) -> DisplayMode:
    """``--resolution`` when given, else the monitor's own mode."""
    if spec:
        return parse_spec(spec)
    mode = (detect or detect_display)()
    if mode is None:
        raise ConsoleError(
            "could not read the monitor's current mode; pass "
            "--resolution WxH@R with the monitor's resolution and refresh")
    return mode
