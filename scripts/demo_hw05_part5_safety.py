#!/usr/bin/env python3

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "code", "mcp"))
sys.path.insert(0, HERE)

from execute_tool import execute_tool
from test_hw05_part4 import BACKENDS


def main():
    allowed = execute_tool(
        "search_recalls",
        {"query": "Blueberries", "limit": 5},
        backends=BACKENDS,
    )
    blocked = execute_tool(
        "search_recalls",
        {"query": "rohan1@gmail.com", "limit": 5},
        backends=BACKENDS,
    )
    print("ALLOWED")
    print(allowed)
    print()
    print("BLOCKED")
    print(blocked)


if __name__ == "__main__":
    main()
