from __future__ import annotations
import json
from goodq4all.steps.common.config_loader import load_configs


def main() -> None:
    cfg = load_configs({})
    print(json.dumps(cfg, ensure_ascii=False))


if __name__ == "__main__":
    main()

