from __future__ import annotations

import sys
from pathlib import Path

from toolkit.app import main as app_main


def _initial_path_from_argv() -> str | None:
    if len(sys.argv) < 2:
        return None
    candidate = Path(sys.argv[1]).expanduser()
    return str(candidate) if candidate.exists() else None


if __name__ == "__main__":
    app_main(initial_path=_initial_path_from_argv())
