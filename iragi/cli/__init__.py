"""Iragi CLI package.

Exposes the command-line application instance.

Example:
    >>> from iragi.cli import app
    >>> app.info.name
    'iragi'
"""

from iragi.cli.main import app, main

__all__ = ["app", "main"]
