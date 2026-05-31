"""Enable `python -m touch_grass ...` (used by `serve-all` to launch children)."""

from .server import main

if __name__ == "__main__":
    main()
