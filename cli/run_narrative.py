from __future__ import annotations

import sys


_MESSAGE = (
    "cli.run_narrative is retired from the tracked runtime surface because it "
    "depends on the removed run-summary backing module. Treat the old narrative "
    "layer as historical until a truthful summary surface is explicitly restored."
)


def main() -> int:
    print(_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
