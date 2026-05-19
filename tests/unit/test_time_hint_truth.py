from __future__ import annotations


def test_audio_time_hints_does_not_treat_music_march_as_calendar_month() -> None:
    from steps.audio_time_hints.step import audio_time_hints

    result = audio_time_hints(
        {"transcript": 'Thank you. ["Pomp and Circumstance March"]'},
        {"audio": {}},
    )

    assert result["time_hints"]["months"] == []
    assert result["time_hints_meta"]["status"] == "none"


def test_audio_time_hints_keeps_contextual_month_reference() -> None:
    from steps.audio_time_hints.step import audio_time_hints

    result = audio_time_hints(
        {"transcript": "We visited the school in March."},
        {"audio": {}},
    )

    assert result["time_hints"]["months"] == ["march"]
    assert result["time_hints_meta"]["status"] == "ok"


def test_audio_time_hints_parses_month_name_date() -> None:
    from steps.audio_time_hints.step import audio_time_hints

    result = audio_time_hints(
        {"transcript": "The tape says December 16, 2002."},
        {"audio": {}},
    )

    assert result["time_hints"]["explicit_dates"] == ["2002-12-16"]
    assert result["time_hints"]["months"] == ["december"]


def test_harmonizer_prefers_visual_time_hints_when_audio_has_no_time_values() -> None:
    from steps.video.cross_modal_harmonizer import _resolve_scene_time_hints

    audio_payload = {
        "time_hints": {
            "explicit_dates": [],
            "times": [],
            "weekdays": [],
            "months": [],
            "relative_phrases": [],
        }
    }
    scene_payload = {
        "keyframe": {
            "time_hints": {
                "explicit_dates": ["2002-12-16"],
                "times": [],
                "weekdays": [],
                "months": ["december"],
                "relative_phrases": [],
            }
        }
    }

    assert _resolve_scene_time_hints(audio_payload, scene_payload) == scene_payload["keyframe"]["time_hints"]


def test_harmonizer_merges_audio_and_visual_time_hints() -> None:
    from steps.video.cross_modal_harmonizer import _resolve_scene_time_hints

    audio_payload = {"time_hints": {"weekdays": ["friday"], "relative_phrases": ["last night"]}}
    scene_payload = {"keyframe": {"time_hints": {"explicit_dates": ["2002-12-16"], "months": ["december"]}}}

    assert _resolve_scene_time_hints(audio_payload, scene_payload) == {
        "weekdays": ["friday"],
        "relative_phrases": ["last night"],
        "explicit_dates": ["2002-12-16"],
        "months": ["december"],
    }


def test_harmonizer_does_not_promote_flat_audio_emotion_distribution() -> None:
    from steps.video.cross_modal_harmonizer import _resolve_audio_emotion

    label, scores = _resolve_audio_emotion(
        {
            "audio_emotion": "angry",
            "emotion_scores": {
                "angry": 0.14,
                "neutral": 0.13,
                "happy": 0.12,
            },
        }
    )

    assert label is None
    assert scores["angry"] == 0.14


def test_harmonizer_promotes_audio_emotion_at_human_review_threshold() -> None:
    from steps.video.cross_modal_harmonizer import _resolve_audio_emotion

    label, scores = _resolve_audio_emotion(
        {
            "audio_emotion": "neutral",
            "emotion_scores": {
                "neutral": 0.74,
                "happy": 0.11,
            },
        }
    )

    assert label == "neutral"
    assert scores["neutral"] == 0.74
