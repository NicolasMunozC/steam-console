#!/bin/sh
# Steam Console installer — no pip, no virtualenv, no build step.
#
# It copies the modules into <prefix>/share/steam-console and writes one small
# launcher into <prefix>/bin, because that is the whole program: the Python
# standard library plus the gamescope and steam already on the machine.
#
# Usage:
#   ./install.sh [--prefix DIR] [--no-desktop] [--terminal] [--uninstall] [--dry-run]
#   curl -fsSL https://raw.githubusercontent.com/NicolasMunozC/steam-console/main/install.sh | sh
set -eu

PREFIX="${PREFIX:-$HOME/.local}"
REPO="https://github.com/NicolasMunozC/steam-console"
BRANCH="main"

WITH_DESKTOP=1
WITH_TERMINAL=0
UNINSTALL=0
DRY=0
TMP=""

say()  { printf '%s\n' "$*"; }
fail() { printf 'install: %s\n' "$*" >&2; exit 1; }
do_it() {
    if [ "$DRY" = 1 ]; then printf '  would: %s\n' "$*"; else "$@"; fi
}

cleanup() {
    if [ -n "$TMP" ]; then rm -rf "$TMP"; fi
}
trap cleanup EXIT INT TERM

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix)     [ $# -ge 2 ] || fail "--prefix needs a directory"
                      PREFIX="$2"; shift 2 ;;
        --prefix=*)   PREFIX="${1#--prefix=}"; shift ;;
        --no-desktop) WITH_DESKTOP=0; shift ;;
        --terminal)   WITH_TERMINAL=1; shift ;;
        --uninstall)  UNINSTALL=1; shift ;;
        --dry-run)    DRY=1; shift ;;
        -h|--help)    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)            fail "unknown option: $1 (try --help)" ;;
    esac
done

BINDIR="$PREFIX/bin"
APPDIR="$PREFIX/share/applications"
LIBDIR="$PREFIX/share/steam-console"
ENTRY="$APPDIR/steam-console.desktop"
ICONDIR="$PREFIX/share/icons/hicolor/scalable/apps"
ICON="$ICONDIR/steam-console.svg"

if [ "$UNINSTALL" = 1 ]; then
    say "Removing $LIBDIR, the launchers and the menu entry"
    do_it rm -rf "$LIBDIR"
    do_it rm -f "$BINDIR/steam-console" "$BINDIR/consola-steam" "$ENTRY" "$ICON"
    say "Done."
    exit 0
fi

# --- what the tool needs ---------------------------------------------------

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    fail "python3 >= 3.11 is required (found $(python3 -V 2>&1))"
fi

for tool in gamescope steam; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        say "warning: $tool is not on PATH — install it before running steam-console"
    fi
done

# --- where the sources come from ------------------------------------------

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ -d "$HERE/src/steam_console" ]; then
    SRC="$HERE"
    say "Installing from $HERE"
elif [ "$DRY" = 1 ]; then
    SRC=""
    say "Would download $REPO ($BRANCH)"
else
    command -v curl >/dev/null 2>&1 || fail "curl is required to download the sources"
    command -v tar >/dev/null 2>&1 || fail "tar is required to unpack the sources"
    say "Downloading $REPO ($BRANCH)"
    TMP=$(mktemp -d)
    curl -fsSL "$REPO/archive/refs/heads/$BRANCH.tar.gz" \
        | tar -xz -C "$TMP" --strip-components=1
    SRC="$TMP"
fi

# --- install --------------------------------------------------------------

say "Installing into $LIBDIR"
do_it mkdir -p "$LIBDIR/src" "$BINDIR"
if [ "$DRY" != 1 ]; then
    rm -rf "$LIBDIR/src/steam_console"
    cp -R "$SRC/src/steam_console" "$LIBDIR/src/"
    rm -rf "$LIBDIR/src/steam_console/__pycache__"
    for doc in README.md LICENSE NOTICE; do
        if [ -f "$SRC/$doc" ]; then cp "$SRC/$doc" "$LIBDIR/"; fi
    done
fi

if [ "$DRY" = 1 ]; then
    say "  would: write $BINDIR/steam-console (+ consola-steam symlink)"
    say "  would: PYTHONPATH=$LIBDIR/src exec python3 -m steam_console \"\$@\""
else
    cat > "$BINDIR/steam-console" <<EOF
#!/bin/sh
# Steam Console launcher — written by install.sh
PYTHONPATH="$LIBDIR/src\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m steam_console "\$@"
EOF
    chmod +x "$BINDIR/steam-console"
    ln -sf steam-console "$BINDIR/consola-steam"
fi

if [ "$WITH_DESKTOP" = 1 ]; then
    say "Adding the menu entry and its icon"
    do_it mkdir -p "$APPDIR" "$ICONDIR"
    if [ "$DRY" = 1 ]; then
        say "  would: write $ENTRY"
        say "  would: write $ICON"
    else
        cp "$SRC/assets/steam-console.svg" "$ICON"

        # Terminal=false is what makes it behave like an app: a launcher that
        # has no terminal configured would otherwise run nothing at all.
        # --terminal keeps Ctrl+C available as a way out of a hung gamescope.
        if [ "$WITH_TERMINAL" = 1 ]; then TERMINAL=true; else TERMINAL=false; fi
        cat > "$ENTRY" <<EOF
[Desktop Entry]
Type=Application
Name=Steam Console (Consola Steam)
GenericName=Console-mode Steam
Comment=Big Picture under fullscreen gamescope, using this machine's Steam
Exec=$BINDIR/steam-console
Icon=steam-console
Terminal=$TERMINAL
Categories=Game;
Keywords=steam;bigpicture;big picture;gamescope;console;consola;
EOF

        if command -v desktop-file-validate >/dev/null 2>&1; then
            desktop-file-validate "$ENTRY" || fail "the desktop entry is invalid"
        fi
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "$APPDIR" >/dev/null 2>&1 || true
        fi
        if command -v gtk-update-icon-cache >/dev/null 2>&1; then
            gtk-update-icon-cache -f -t "$PREFIX/share/icons/hicolor" >/dev/null 2>&1 || true
        fi
    fi
fi

# --- done -----------------------------------------------------------------

say ""
say "Installed. Run it with: steam-console"
say "Preview the exact gamescope command with: steam-console --print-only"
if [ "$WITH_DESKTOP" = 1 ]; then
    say 'Or find it in your launcher (SUPER on Hyprland, the app menu elsewhere):'
    say '  "Steam Console (Consola Steam)"'
fi

case ":${PATH}:" in
    *":$BINDIR:"*) ;;
    *) say ""
       say "warning: $BINDIR is not on PATH. Add it once:"
       say "  fish:  fish_add_path $BINDIR"
       say "  sh:    export PATH=\"$BINDIR:\$PATH\"" ;;
esac

say ""
say "Uninstall later with: $0 --uninstall"
