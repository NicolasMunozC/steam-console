# Steam Console (Consola Steam)

Play Steam like a real console on your own machine: one fullscreen
[gamescope](https://github.com/ValveSoftware/gamescope) window running **your**
Steam in Big Picture. No container, no streaming, no second Steam, nothing to
synchronise — the same login, `compatdata` prefixes, non-Steam shortcuts, grid
art, Proton mapping and controller layouts the desktop already has.

```console
$ steam-console
Steam Console on 3440x1440@180 (DP-3)
Closing Steam (one Steam at a time)…
  exit: close Big Picture, or Ctrl+C here
```

## Why not just Big Picture on the desktop

Big Picture in a window is an application on a desktop. Big Picture inside
gamescope is a console: Steam believes it owns the display, so its display panel
offers resolution, refresh, framerate limit and HDR; games are forced to the
window; and — the reason this exists — **the Steam overlay works**: pressing the
guide button hides the game, shows the overlay above it, and closing the overlay
restores the game.

That last part needs `-e` (`--steam`, gamescope's Steam integration). Without it
the overlay is an ordinary window and stays *below* a fullscreen game, which is
exactly how it behaves in plain desktop Big Picture.

## Requirements

- Linux with a running Wayland (or X11) session
- `gamescope` and `steam` on `PATH`
- one of `hyprctl` (Hyprland), `swaymsg` (sway) or `xrandr` (X11) to read the
  monitor mode

## Install

```console
$ python3 -m venv .venv
$ .venv/bin/pip install -e .
$ .venv/bin/steam-console --print-only
```

`steam-console` and `consola-steam` are the same command.

## Usage

```console
$ steam-console                      # the focused monitor's own mode
$ steam-console --print-only         # show the gamescope line, touch nothing
$ steam-console --resolution 1920x1080@60
$ steam-console --resolution deck    # or 1080p60, 1080p120, 1440p60, 4k60
$ steam-console --keep-steam         # do not close Steam first (it must be idle)
$ steam-console --steam-flags "-gamepadui -noreactlogin"
```

Exit by closing Big Picture (Steam exits, gamescope follows) or with Ctrl+C.

## How the mode is chosen

The mode is read from the focused monitor, first probe that answers:

| Session | Probe |
|---|---|
| Hyprland | `hyprctl monitors -j` |
| sway | `swaymsg -t get_outputs --raw` |
| X11 | `xrandr --current` |

gamescope then opens at exactly that size on both sides (`-W/-H` for its output,
`-w/-h` for the render target). Opening at any other size would mean rendering
at one resolution and scaling to another — the display panel would report one
number while the monitor showed another.

If no probe can read the mode there is no default: the command stops and asks
for `--resolution WxH@R`. A guess here is precisely the bug this avoids.

## What it does not do

The desktop is still underneath, so:

- notifications can still appear over the game;
- alt-tab still works (which is also the escape hatch if something hangs);
- a second monitor keeps showing the desktop;
- HDR and VRR do not reach the physical panel through a nested window, and the
  refresh is presented by your compositor, so a value above the monitor's own
  does nothing.

Removing those needs gamescope as the *session compositor* — a login session
with no desktop around it, the way SteamOS does it. The flags this tool prints
are the ones that session needs too.

## Flag parity

The gamescope line mirrors
[podstage](https://github.com/slooock-dev/podstage)'s
`containers/runtime/runner.sh`, the line a podstage streaming session uses. Keeping the two in step is deliberate: it is
where the `-e` overlay behaviour, `--force-windows-fullscreen` and
`--expose-wayland` were proven. If upstream changes that line, change this one.

```console
$ gamescope --backend wayland -W 3440 -H 1440 -w 3440 -h 1440 -r 180 \
    -C 3000 --expose-wayland --force-windows-fullscreen -e -f -- steam -gamepadui
```

## Attribution

Steam Console is by **NicolasMunozC** — https://github.com/NicolasMunozC/steam-console

Use it, fork it, embed it, ship it: it is MIT licensed and meant to be used.

If you do, credit the original author by name with a link to this repository and
keep the `LICENSE` and `NOTICE` files. The MIT License already requires the
copyright notice to travel with every copy and every substantial portion of the
code, so a fork that rebrands the project still has to keep it — and a fork must
not present this work as its own.

The licence can grant that; it cannot make a fork advertise you in its own UI.
If you need that promise from downstream users, ask before forking — it is
cheaper than a custom licence nobody will adopt.

## Tests

```console
$ .venv/bin/pip install -e ".[dev]"
$ .venv/bin/python -m pytest -q
```
