import logging

from steps.video.entity_extractor import EntityExtractor


def test_entity_extractor_labels_zero_entity_visual_pass_as_preliminary(caplog) -> None:
    caplog.set_level(logging.INFO, logger="steps.video.entity_extractor")

    extractor = EntityExtractor()
    entities = extractor.extract_from_scene({"caption": "and the but"}, "scene-zero", "video-zero")

    assert entities == []
    assert "Preliminary extraction pass resolved 0 entities" in caplog.text
    assert "later transcript/temporal KG passes may still resolve entities" in caplog.text
    assert not [
        record
        for record in caplog.records
        if record.name == "steps.video.entity_extractor" and record.levelno >= logging.WARNING
    ]
