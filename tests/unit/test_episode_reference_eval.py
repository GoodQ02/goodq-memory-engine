from __future__ import annotations

from scripts.diagnostics import episode_reference_eval as ref_eval


def test_extract_projected_scenes_flattens_video_result_list() -> None:
    projected_output = [
        {
            "video_id": "vid-1",
            "scenes": [
                {"index": 0, "summary": "Conversation about cold medication.", "tags": ["cold medication"]},
                {"index": 1, "summary": "Party conversation.", "tags": ["party"]},
            ],
        }
    ]

    scenes = ref_eval._extract_projected_scenes(projected_output)

    assert [scene["index"] for scene in scenes] == [0, 1]
    assert scenes[0]["summary"] == "Conversation about cold medication."


def test_evaluate_reference_episode_marks_projected_visible_for_nested_scene_output() -> None:
    anchor = {
        "episode_code": "03x10",
        "title": "The Stranded",
        "reference_summary": "Reference summary",
        "beats": [],
        "salient_concepts": [
            {
                "concept": "cold medication",
                "tier": "primary",
                "weight": 1.0,
                "aliases": ["medicine"],
            }
        ],
    }
    canonical_manifest = {
        "scenes": [
            {
                "index": 0,
                "scene_context_llm": {
                    "narrative_summary": "Spoken monologue about cold medication.",
                    "key_moments": ["Speaker delivers a monologue about cold medication"],
                    "context_tags": ["cold medication"],
                    "primary_tags": ["cold medication"],
                    "contextual_tags": [],
                    "structural_tags": [],
                },
                "scene_context_arbitration": {
                    "hypotheses": [{"claim": "cold medication", "weight": "primary"}]
                },
            }
        ]
    }
    projected_output = [
        {
            "video_id": "vid-1",
            "scenes": [
                {
                    "index": 0,
                    "summary": "Spoken monologue about cold medication.",
                    "tags": ["cold medication"],
                    "key_moments": ["Speaker delivers a monologue about cold medication"],
                }
            ],
        }
    ]

    result = ref_eval._evaluate_reference_episode(anchor, canonical_manifest, projected_output)

    assert result["salience_results"][0]["projected_visible"] is True
    assert result["metrics"]["projected_visible_concepts"] == 1
