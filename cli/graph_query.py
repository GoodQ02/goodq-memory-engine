"""Retired compatibility shell for the historical graph-query surface."""

import sys


def main() -> None:
    sys.stderr.write(
        "cli.graph_query is retired because the historical lib.graph_query module "
        "is no longer present in the active runtime.\n"
        "Use canonical KG-backed read surfaces or direct SQLite/operator tooling "
        "instead of this legacy shell.\n"
    )
    raise SystemExit(2)


if __name__ == "__main__":
    main()
