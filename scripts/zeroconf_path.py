"""Load the replaceable LGPL Zeroconf package from beside the executable."""

from pathlib import Path
import sys


if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).resolve().parent))
