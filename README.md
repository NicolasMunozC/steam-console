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
  exit: the power menu's “Switch to desktop”, or Ctrl+C here
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
- a Steam that already works: installed, **logged in**, Steam Guard passed, the
  libraries you want mounted

That last one is not a formality. Nothing here installs Steam or creates a
second one: it runs the `steam` you have, with the account, the `compatdata`
prefixes and the shortcuts that client already knows. The first login is a
keyboard job on a UI built for a gamepad, so do it on the desktop, where you
have a keyboard — the console is for after that.

## Install

One command. No pip, no virtualenv, no build step — it copies three modules into
`~/.local/share/steam-console` and puts `steam-console` in `~/.local/bin`:

```console
$ curl -fsSL https://raw.githubusercontent.com/NicolasMunozC/steam-console/main/install.sh | sh
```

From a clone it is the same thing:

```console
$ ./install.sh
```

Then:

```console
$ steam-console
```

`steam-console` and `consola-steam` are the same command, and the installer adds
a **Steam Console (Consola Steam)** entry with its own icon to
`~/.local/share/applications` — the standard XDG location, so it shows up in the
SUPER launcher on Hyprland and in the application menu on any other desktop,
and it behaves like any other app: no terminal window, no path to remember.

| Option | Effect |
|---|---|
| `--prefix DIR` | install under `DIR` instead of `~/.local` |
| `--no-desktop` | skip the menu entry |
| `--terminal` | run the entry in a terminal (`Terminal=true`) |
| `--dry-run` | print what it would do |
| `--uninstall` | remove the modules, the launchers and the menu entry |

Nothing is compiled and nothing is downloaded at runtime: the program is Python
standard library plus the `gamescope` and `steam` already on your machine. The
installer only warns when those two are missing.

### Other installs

```console
$ pipx install git+https://github.com/NicolasMunozC/steam-console
```

For working on the code, use the project's own environment:

```console
$ python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
$ .venv/bin/python -m pytest -q
```

## Usage

```console
$ steam-console                      # the focused monitor's own mode
$ steam-console --print-only         # show the gamescope line, touch nothing
$ steam-console --resolution 1920x1080@60
$ steam-console --resolution deck    # or 1080p60, 1080p120, 1440p60, 4k60
$ steam-console --no-steamos         # keep Bluetooth; exit with Ctrl+C
$ steam-console --keep-steam         # do not close Steam first (it must be idle)
$ steam-console --steam-flags "-gamepadui -noreactlogin"
```

You leave with the power menu's **Switch to desktop**, or with Ctrl+C. See
[Leaving the console](#leaving-the-console).

## Leaving the console

The power menu's **Switch to desktop** is the exit: Steam quits and gamescope
follows it back to your desktop. Ctrl+C in the terminal that started it does the
same thing.

Two conditions make that entry work, and both are handled for you:

- Steam has to believe it is on a Deck (`-steamos3`); without that it never runs
  the switch at all, and the dialog waits forever;
- something has to answer the switch: Steam runs a helper named
  `steamos-session-select`, which a desktop machine does not have.

Deck mode is therefore the default. Each session writes that helper into a
temporary directory (preferring `$XDG_RUNTIME_DIR`), checks that it is executable
and not merely writable, puts it first on the session's `PATH`, and prepares it
before Steam is closed — so a machine with no usable temporary directory fails
while the desktop client is still open, not after. Nothing lands in
`~/.local/bin`, and the directory is removed when the session ends.

### The first Deck-mode run and Bluetooth

Deck mode also makes Steam configure itself like a Deck, and on its first run it
shows the controller and audio setup. On the machine this was developed on, that
first run **powered the Bluetooth radio off**, disconnecting the very controllers
the setup was asking about: `Powered: yes` before, `Powered: no` after, measured
with `steam -steamos3 -gamepadui` alone and no gamescope involved.

It has not happened again since. The second launch of the same session left the
radio on and never showed the setup, and choosing Switch to desktop closed it
cleanly both times. The likely cause is the first-run setup touching the radio,
not Deck mode itself. It may also depend on your adapter and controllers: this is
one machine's evidence, not a rule.

If it happens to you: turn Bluetooth back on (Deck quick-access menu, or
`bluetoothctl power on`), finish the setup, and the next launch should be clean.

**If you would rather not risk it at all**, opt out:

```console
$ steam-console --no-steamos
```

Steam then runs as an ordinary Big Picture client: the Bluetooth radio is never
touched and the power menu's Switch to desktop does nothing, because Steam only
calls the helper in Deck mode. Leave that session by closing Big Picture or with
Ctrl+C — the launcher prints that reminder every time.

### One Steam at a time

The desktop client is closed for you: `steam -shutdown`, then up to 45 seconds
waiting for its `steamwebhelper` process to disappear. Closing Steam yourself
first is not required. `--keep-steam` is the opposite case: it refuses to run
while a Steam is up, for a client you know is idle.

If the client is still there when the wait runs out, the session opens anyway
with a warning — Big Picture then joins the client that was already running,
which can look like nothing happened. Quit Steam by hand and run the command
again.

## Running it like an app

`steam-console` from a terminal stays the honest way to run it, and the only way
to see its output. The installed entry is for the couch: pick it from the
launcher, Big Picture opens fullscreen, close Big Picture to leave.

The entry uses `Terminal=false` on purpose — a launcher with no terminal
configured would otherwise start nothing at all. The trade is that there is no
Ctrl+C to fall back on if gamescope wedges; install with `--terminal` if you want
that escape hatch. From the couch, the way out is the power menu's **Switch to
desktop**, which needs no terminal at all. `pkill gamescope` clears a wedged
session either way.

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

- the power menu acts on this machine: Shut down, Restart and Suspend reach the
  real desktop through logind, because this is your own session and not a
  sandbox. The console does not filter them;
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
    -C 3000 --expose-wayland --force-windows-fullscreen -e -f -- \
    steam -steamos3 -gamepadui
```

The Steam flags match podstage, plus `-steamos3`: that is what makes the power
menu's exit call the helper instead of hanging (see
[Leaving the console](#leaving-the-console)). `--no-steamos` drops it; podstage
streams into a session it controls itself and needs neither.

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
