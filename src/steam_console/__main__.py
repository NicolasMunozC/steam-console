"""``python -m steam_console``: what the installed wrapper runs."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
