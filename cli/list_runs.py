from __future__ import annotations

import sys


_MESSAGE = (
    "cli.list_runs is retired from the tracked runtime surface because the old "
    "run-index backing module is gone. Use runtime artifacts, temporal indexes, "
    "or the active API/runtime read surfaces instead."
)


def main() -> int:
    print(_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
