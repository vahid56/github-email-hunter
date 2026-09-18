"""Legacy script entry point.

Prefer the installed ``ghmail`` command or ``python -m ghmail``. This file lets
you still run ``python ghmail.py <username>`` straight from a source checkout.
"""

from ghmail.cli import main

if __name__ == "__main__":
    raise SystemExit(main())