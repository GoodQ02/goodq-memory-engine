from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from scripts.config_schema import SavedCollectionConfig


def test_saved_collections_are_navigation_without_store_access(monkeypatch):
    from api.routes import system
    from steps.common import config_loader

    collection = dict(name="Movie one", retro_url="http://127.0.0.1:30000/ui/retro_console_v1/",
                      identity_url="http://127.0.0.1:30040/ui/identity_workbench/")
    monkeypatch.setattr(config_loader, "load_configs", lambda _: {"ui": {"saved_collections": [collection]}})
    monkeypatch.setattr(system, "get_data_loader", lambda: pytest.fail("Navigation must not access stores"))
    app = FastAPI()
    app.include_router(system.router)
    response = TestClient(app).get("/api/system/saved-collections")
    assert response.status_code == 200
    assert response.json() == {"collections": [collection]}


@pytest.mark.parametrize("url", ["https://example.com/ui/retro_console_v1/",
    "http://127.0.0.1:30000/api/ingest/submit", "javascript:alert(1)",
    "http://user:secret@127.0.0.1:30000/ui/retro_console_v1/"])
def test_saved_collection_rejects_nonlocal_or_nonview_destinations(url):
    with pytest.raises(ValidationError):
        SavedCollectionConfig(name="Movie", retro_url=url,
                              identity_url="http://127.0.0.1:30040/ui/identity_workbench/")
