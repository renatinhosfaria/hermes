"""Local Hermes extension; no model-facing tools or customer messages."""

import sys
from pathlib import Path


def register(ctx):
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import lifecycle_runtime

    if Path(lifecycle_runtime.__file__).resolve() != root / "lifecycle_runtime.py":
        raise RuntimeError("Session lifecycle module collision")
    from hermes_constants import get_hermes_home

    lifecycle_runtime.start(ctx, Path(get_hermes_home()))
