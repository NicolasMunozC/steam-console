"""Reading the monitor mode, and refusing to guess one."""

import json

import pytest

from steam_console import display

HYPR = json.dumps([{
    "id": 0, "name": "DP-3", "width": 3440, "height": 1440,
    "refreshRate": 179.99, "focused": True,
}])

HYPR_TWO = json.dumps([
    {"id": 0, "name": "DP-3", "width": 3440, "height": 1440,
     "refreshRate": 179.99, "focused": False},
    {"id": 1, "name": "HDMI-A-1", "width": 1920, "height": 1080,
     "refreshRate": 60.0, "focused": True},
])

SWAY = json.dumps([{
    "name": "DP-3", "focused": True,
    "current_mode": {"width": 2560, "height": 1440, "refresh": 143976},
}])

XRANDR = """\
Screen 0: minimum 320 x 200, current 3440 x 1440, maximum 16384 x 16384
HDMI-A-1 connected 1920x1080+3440+0 (normal left inverted right x axis y axis) 520mm x 290mm
   1920x1080     60.00*+
DP-3 connected primary 3440x1440+0+0 (normal left inverted right x axis y axis) 810mm x 350mm
   3440x1440     59.97 + 179.99*+
   2560x1440    120.00
"""


def fake_run(table):
    """A ``_run`` stand-in dispatching on argv[0]."""
    def run(argv):
        return table.get(argv[0], "")
    return run


def test_reads_the_focused_hyprland_monitor(monkeypatch):
    monkeypatch.setattr(display, "_run", fake_run({"hyprctl": HYPR}))

    assert display.detect_display() == display.DisplayMode(3440, 1440, 180, "DP-3")


def test_focus_decides_the_monitor_not_the_list_order(monkeypatch):
    monkeypatch.setattr(display, "_run", fake_run({"hyprctl": HYPR_TWO}))

    mode = display.detect_display()

    assert (mode.width, mode.height, mode.refresh, mode.output) == (
        1920, 1080, 60, "HDMI-A-1")


def test_understands_sway(monkeypatch):
    monkeypatch.setattr(display, "_run", fake_run({"swaymsg": SWAY}))

    mode = display.detect_display()

    # sway reports the refresh in mHz.
    assert (mode.width, mode.height, mode.refresh) == (2560, 1440, 144)


def test_falls_back_to_the_xrandr_primary_output(monkeypatch):
    monkeypatch.setattr(display, "_run", fake_run({"xrandr": XRANDR}))

    mode = display.detect_display()

    assert (mode.width, mode.height, mode.refresh, mode.output) == (
        3440, 1440, 180, "DP-3")


def test_no_probe_reports_a_mode(monkeypatch):
    monkeypatch.setattr(display, "_run", fake_run({}))

    assert display.detect_display() is None


def test_garbage_output_is_not_a_mode(monkeypatch):
    monkeypatch.setattr(display, "_run",
                        fake_run({"hyprctl": "{not json", "xrandr": ""}))

    assert display.detect_display() is None


@pytest.mark.parametrize("spec,expected", [
    ("1920x1080@60", (1920, 1080, 60)),
    ("2560x1440", (2560, 1440, 60)),
    ("3440x1440@179.99", (3440, 1440, 180)),
    ("deck", (1280, 800, 60)),
    ("4K60", (3840, 2160, 60)),
])
def test_resolution_specs(spec, expected):
    mode = display.parse_spec(spec)

    assert (mode.width, mode.height, mode.refresh) == expected


def test_a_bad_spec_says_what_it_wants():
    with pytest.raises(ValueError) as err:
        display.parse_spec("big")

    assert "WxH@R" in str(err.value)


def test_an_override_beats_detection():
    def must_not_detect():
        pytest.fail("detection must not run when --resolution is given")

    mode = display.resolve_display("1920x1080@60", detect=must_not_detect)

    assert mode == display.DisplayMode(1920, 1080, 60)


def test_no_mode_is_an_error_not_a_default():
    with pytest.raises(display.ConsoleError) as err:
        display.resolve_display(None, detect=lambda: None)

    assert "--resolution" in str(err.value)
