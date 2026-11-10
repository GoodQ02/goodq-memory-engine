"""Caption grounding markup never reaches users; saved model text is not rewritten."""
import json

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from lib.grounding_markup import has_grounding_markup, strip_grounding_markup, strip_grounding_markup_json

SAVED_MOVIE_ONE = ("<ref>A white car</ref><box><155><295><712><620></box> is parked on a street surrounded by trees.")
SAVED_MOVIE_TWO = ("They are holding up <ref>two balloons</ref><box><190><36><371><344>,<317><228><481><502></box> "
                   "near the couch.")


@pytest.mark.parametrize("raw, expected", [
    (SAVED_MOVIE_ONE, "A white car is parked on a street surrounded by trees."),
    (SAVED_MOVIE_TWO, "They are holding up two balloons near the couch."),
    ("<ref>A dark brown wall</ref><box>(5,0),(1000,1000)</box> with no visible people.",
     "A dark brown wall with no visible people."),
    ("Plain caption with a <b>tag</b> and 3 < 4 > 2.", "Plain caption with a <b>tag</b> and 3 < 4 > 2."),
])
def test_strip_keeps_described_phrase_and_drops_coordinates(raw, expected):
    assert strip_grounding_markup(raw) == expected
    assert not has_grounding_markup(strip_grounding_markup(raw))


def test_json_strip_preserves_document_and_other_fields():
    document = {"caption": SAVED_MOVIE_ONE, "summary": "Visual: " + SAVED_MOVIE_TWO, "score": 0.125,
                "quote": 'He said "<ref>" is a word', "nested": [{"visual_caption": SAVED_MOVIE_TWO}]}
    cleaned = json.loads(strip_grounding_markup_json(json.dumps(document).encode()))
    assert cleaned["caption"] == "A white car is parked on a street surrounded by trees."
    assert cleaned["nested"][0]["visual_caption"].startswith("They are holding up two balloons ")
    assert cleaned["score"] == 0.125 and set(cleaned) == set(document)
    unchanged = json.dumps({"caption": "no markup"}).encode()
    assert strip_grounding_markup_json(unchanged) is unchanged


def test_production_app_cleans_served_json_but_not_other_media():
    from api.main import GroundingMarkupMiddleware, app as production

    assert any(m.cls is GroundingMarkupMiddleware for m in production.user_middleware)
    app = FastAPI()
    app.add_middleware(GroundingMarkupMiddleware)

    @app.get("/scene")
    def scene():
        return {"visual_caption": SAVED_MOVIE_ONE, "summary": SAVED_MOVIE_TWO}

    @app.get("/explicit")
    def explicit():
        return JSONResponse({"caption": SAVED_MOVIE_TWO}, status_code=207, headers={"x-goodq-unavailable-sources": "[]"})

    @app.get("/text")
    def text():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(SAVED_MOVIE_ONE)

    client = TestClient(app)
    body = client.get("/scene")
    assert body.json() == {"visual_caption": "A white car is parked on a street surrounded by trees.",
                           "summary": "They are holding up two balloons near the couch."}
    assert int(body.headers["content-length"]) == len(body.content)
    explicit_response = client.get("/explicit")
    assert explicit_response.status_code == 207
    assert explicit_response.headers["x-goodq-unavailable-sources"] == "[]"
    assert "<box>" not in explicit_response.text
    assert client.get("/text").text == SAVED_MOVIE_ONE  # Only JSON responses are rewritten.


def test_caption_producer_removes_markup_and_records_it(tmp_path, monkeypatch):
    from PIL import Image
    from steps.image_caption import step

    image = tmp_path / "frame.png"
    Image.effect_noise((64, 64), 80).convert("RGB").save(image)
    monkeypatch.setattr(step, "_load_model", lambda cfg: False)
    monkeypatch.setattr(step, "_describe", lambda img: (SAVED_MOVIE_ONE, 40))
    monkeypatch.setitem(step._MODEL, "device", "cpu")
    result = step._caption_one({"source_path": str(image), "timestamp": 1.0}, {})
    assert result["caption"] == "A white car is parked on a street surrounded by trees."
    assert result["caption_meta"]["grounding_markup_removed"] is True
    assert result["caption_meta"]["status"] == "ok"
    monkeypatch.setattr(step, "_describe", lambda img: ("A kitchen with a table.", 8))
    plain = step._caption_one({"source_path": str(image)}, {})
    assert plain["caption"] == "A kitchen with a table." and "grounding_markup_removed" not in plain["caption_meta"]
