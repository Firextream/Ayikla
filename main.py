"""Executable entry point; preserve startup diagnostics in automated verification."""

import sys
import traceback
from pathlib import Path

if __name__ == "__main__":
    try:
        from ayikla.__main__ import main
        exit_code = main()
    except Exception:
        if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
            output = Path(sys.argv[2])
            output.mkdir(parents=True, exist_ok=True)
            (output / "startup-error.txt").write_text(traceback.format_exc(), "utf-8")
            exit_code = 1
        else:
            raise
    raise SystemExit(exit_code)
