from __future__ import annotations
import json
import os
from typing import Any

try:
    from zenml.materializers.base_materializer import BaseMaterializer  # type: ignore
except Exception:  # fallback import path for older ZenML
    from zenml.materializers import BaseMaterializer  # type: ignore


class JSONMaterializer(BaseMaterializer):
    """Simple JSON materializer for dict/list artifacts.

    Saves artifacts as a pretty-printed data.json for easy inspection in the UI.
    """

    ASSOCIATED_TYPES = (dict, list)
    URI_FNAME = "data.json"

    def load(self, data_type: type) -> Any:  # noqa: D401
        path = os.path.join(self.uri, self.URI_FNAME)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, obj: Any) -> None:  # noqa: D401
        os.makedirs(self.uri, exist_ok=True)
        path = os.path.join(self.uri, self.URI_FNAME)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)

