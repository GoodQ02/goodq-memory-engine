from __future__ import annotations
import json
from typing import Any, Dict, List


def main() -> None:
    from steps.common.config_loader import load_configs
    from steps.discover_sources.step import discover_sources

    cfg = load_configs({})
    items: List[Dict[str, Any]] = discover_sources(cfg)
    print(json.dumps(items, ensure_ascii=False))


if __name__ == "__main__":
    main()
