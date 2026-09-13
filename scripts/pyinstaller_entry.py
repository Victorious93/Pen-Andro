"""Entry point for PyInstaller builds of the pen-andro CLI.

PyInstaller needs a script file to build from, not a module `-m` target, so
this just calls into the real entry point. The GUI (Tkinter) and web
dashboard (Flask) aren't bundled here — see CONTRIBUTING.md for why.
"""
from pen_andro.cli import main

if __name__ == "__main__":
    main()
