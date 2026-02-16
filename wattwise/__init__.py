"""
WattWise - A CLI tool for monitoring power usage of devices connected to smart plugs.

This package allows users to monitor power consumption in real-time
from the command line, either directly from a TP-Link Kasa smart plug or
through an existing Home Assistant setup.
"""

__version__ = "0.1.5"
__author__ = "Naveen"
__email__ = "hey@naveen.ing"


def get_version() -> str:
    """Return the current version of the package."""
    return __version__


def main() -> None:
    """Entry point for the application."""
    from .cli import main as cli_main

    cli_main()
