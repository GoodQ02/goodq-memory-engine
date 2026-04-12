from __future__ import annotations

from scripts import season3_feature_ladder as ladder


def test_generic_context_detected_rejects_unsupported_social_roles() -> None:
    assert ladder._generic_context_detected(  # type: ignore[attr-defined]
        [
            {
                "full_transcript": "Why are you whispering? What does that mean?",
                "scene_context_llm": {
                    "narrative_summary": "Conversation about whispering.",
                    "activity_description": "Friends talk indoors about renting a car.",
                    "emotional_arc": "mild tension",
                    "key_moments": ["The friends argue about the rental car"],
                    "context_tags": ["friends", "rental car"],
                },
            }
        ]
    )


def test_generic_context_detected_allows_transcript_supported_social_roles() -> None:
    assert not ladder._generic_context_detected(  # type: ignore[attr-defined]
        [
            {
                "full_transcript": "Why do you need more friends? You've got plenty of friends.",
                "scene_context_llm": {
                    "narrative_summary": "Kitchen conversation about condo.",
                    "activity_description": "Friends talk in the kitchen about the condo.",
                    "emotional_arc": "mild tension",
                    "key_moments": ["Friends talk in the kitchen"],
                    "context_tags": ["friends", "kitchen", "condo"],
                },
            }
        ]
    )


def test_select_plan_supports_single_feature_campaign() -> None:
    plan = ladder._select_plan(  # type: ignore[attr-defined]
        None,
        ("03x03", "03x04", "03x05", "03x06", "03x07"),
        "scene_context_llm",
    )

    assert [step.episode_prefix for step in plan] == ["03x03", "03x04", "03x05", "03x06", "03x07"]
    assert all(step.feature_name == "scene_context_llm" for step in plan)
    assert all(step.enable_scene_context_analysis for step in plan)


def test_select_plan_can_resume_custom_campaign() -> None:
    plan = ladder._select_plan(  # type: ignore[attr-defined]
        "03x05",
        ("03x03", "03x04", "03x05", "03x06", "03x07"),
        "scene_context_llm",
    )

    assert [step.episode_prefix for step in plan] == ["03x05", "03x06", "03x07"]
