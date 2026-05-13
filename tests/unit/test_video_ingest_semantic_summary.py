from steps.video_ingest.step import _summarize_video


def test_video_ingest_summary_filters_placeholder_audio_entities():
    result = _summarize_video(
        {
            "video": "sample.mp4",
            "video_hash": "video_hash",
            "frames": [],
            "scenes": [],
            "audio": {
                "tags": ["Apartment", "Well"],
                "entities": ["SPEAKER_00", "FACE_1", "Jerry", "Well"],
            },
        }
    )

    assert result["tags_top"] == [("Apartment", 1)]
    assert result["entities_top"] == [("Jerry", 1)]
