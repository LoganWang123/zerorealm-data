#!/usr/bin/env python
"""Thin entrypoint: python discover.py --query 智能柜 --dry-run"""

from discovery.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
