from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def atomic_write_json(path: Path, data: Dict[str, Any], *, indent: int = 2) -> None:
    """Write JSON payload atomically using same-directory temp file + os.replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    os.replace(tmp, target)
