"""
Root-level monitor.py shim.

Delegates to app.monitor so the project can be run as:
  python monitor.py --once
  python monitor.py --watch
  ...
from the project root directory.
"""

from app.monitor import main

if __name__ == "__main__":
    main()
