"""Single source of truth for the application version.

Read by:
- pyproject.toml (NO — pyproject is the primary; this module mirrors it at runtime)
- build.ps1 (reads from pyproject.toml, passes to iscc.exe as /DAppVersion)
- Future About dialog / hamburger menu footer (runtime read)

Keep the literal string in sync with [project].version in pyproject.toml.
A later phase could auto-derive via importlib.metadata, but for a personal app
the single-literal approach is simpler and works inside PyInstaller bundles
where importlib.metadata paths are quirky.
"""
__version__ = "2.0.0"
