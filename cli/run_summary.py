from __future__ import annotations

import sys


_MESSAGE = (
    "cli.run_summary is retired from the tracked runtime surface because the old "
    "run-summary backing module is gone. Use persisted observability artifacts "
    "or active read-only API surfaces instead."
)


def main() -> int:
    print(_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
