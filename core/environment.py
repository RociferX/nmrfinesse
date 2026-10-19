"""Read environment variables used by NMRFinesse."""

from __future__ import annotations

import os


def get_environment_value(name: str, default: str = "") -> str:
    """Return an environment variable or its default value."""
    return os.environ.get(name, default)


__all__ = ["get_environment_value"]
