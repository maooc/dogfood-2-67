"""envsync entry point.

This module provides the entry point for running envsync as a module.

Example:
    python -m envsync
"""

from .cli import app


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
