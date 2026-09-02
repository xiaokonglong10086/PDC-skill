#!/usr/bin/env python3
"""Stable public CI entrypoint for PDC releases."""

from public_preview_ci import main


if __name__ == "__main__":
    raise SystemExit(main())
