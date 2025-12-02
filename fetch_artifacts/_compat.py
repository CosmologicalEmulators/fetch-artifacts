"""Compatibility imports for TOML parsing."""

# Reading TOML (Python 3.11+ has tomllib built-in)
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

# Writing TOML (requires tomlkit for preserving formatting)
try:
    import tomlkit
except ImportError:
    tomlkit = None
