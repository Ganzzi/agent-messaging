#!/usr/bin/env python3
"""Deprecated compatibility entrypoint.

Use scripts/manual_client_demo.py instead.
"""

import asyncio
import warnings

from scripts.manual_client_demo import main


if __name__ == "__main__":
    warnings.warn(
        "scripts/test_client.py is deprecated. Use scripts/manual_client_demo.py instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    asyncio.run(main())
