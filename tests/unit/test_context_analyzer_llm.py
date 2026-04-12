from __future__ import annotations

from typing import Any

from steps.common import context_analyzer_llm as analyzer


def test_build_scene_context_prompts_enforces_grounded_dry_contract() -> None:
    system_prompt, user_prompt = analyzer._build_scene_context_prompts(  # type: ignore[attr-defined]
        {
            "index": 2,
            "start": 65.24,
            "end": 95.44,
            "caption": "two women are standing in a room with a blue backpack",
            "transcript": "Welcome to Florida. We waited 35 minutes in the rental car place.",
            "objects": [{"label": "person"}, {"label": "backpack"}],
            "face_count": 2,
            "emotions": [{"label": "angry", "score": 0.72}],
            "speakers": ["SPEAKER_00", "SPEAKER_01"],
        }
    )

    assert "EVIDENCE PRIORITY (STRICT)" in system_prompt
    assert "Transcript (highest authority)" in system_prompt
    assert "Caption (lowest authority, may be incorrect)" in system_prompt
    assert "Do not infer family roles, friendships, marriages, jobs, or social relationships" in system_prompt
    assert "Do not infer locations beyond what the caption or transcript explicitly supports" in system_prompt
    assert "Do not rewrite a conversation into a social event" in system_prompt
    assert "Do not use interpretive verbs like waiting, discussing, thinking, feeling, planning, or arguing" in system_prompt
    assert "dry operator-note style JSON" in system_prompt

    assert "Visible caption:" in user_prompt
    assert "Visible objects:" in user_prompt
    assert "Transcript excerpt:" in user_prompt
    assert "Transcript topic hints:" in user_prompt
    assert "Audio emotion signal:" in user_prompt
    assert "narrative_summary MUST mention that topic" in user_prompt
    assert 'Minimal visual or dialogue content.' in user_prompt
    assert "- relationships:" not in user_prompt
    assert '"relationships"' not in user_prompt
    assert '"context_tags": ["indoor conversation", "rental car", "living room"]' in user_prompt


def test_analyze_scene_context_llm_uses_new_prompt_contract(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"narrative_summary":"Group conversation in a living room about a rental car.",'
                                '"key_moments":["People greet each other indoors","They argue about the rental car"],'
                                '"emotional_arc":"mild tension during conversation",'
                                '"context_tags":["indoor conversation","rental car","living room"],'
                                '"activity_description":"People talk indoors about travel and a rental car."}'
                            )
                        }
                    }
                ]
            }

    def _fake_post(url: str, json: dict[str, Any], timeout: int) -> _Response:
        captured["url"] = url
        captured["payload"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 3,
            "start": 95.44,
            "end": 126.0,
            "caption": "a woman standing in a living room with a man",
            "transcript": "How much is a rental car? I don't know. Twenty-five bucks a day.",
            "objects": [{"label": "person"}],
            "face_count": 2,
            "emotions": [{"label": "surprise", "score": 0.6}],
            "speakers": ["SPEAKER_02", "SPEAKER_01"],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    assert captured["url"] == "http://localhost:38005/v1/chat/completions"
    assert captured["timeout"] == 12
    assert captured["payload"]["temperature"] == 0.1

    system_prompt = captured["payload"]["messages"][0]["content"]
    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "EVIDENCE PRIORITY (STRICT)" in system_prompt
    assert "Do not infer family roles, friendships, marriages, jobs, or social relationships" in system_prompt
    assert "Do not use interpretive verbs like waiting, discussing, thinking, feeling, planning, or arguing" in system_prompt
    assert "- relationships:" not in user_prompt
    assert '"relationships"' not in user_prompt
    assert "Transcript topic hints:" in user_prompt
    assert "narrative_summary MUST mention that topic" in user_prompt
    assert "Return ONLY a JSON object with exactly these keys" in user_prompt

    assert result == {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["People greet each other indoors", "They argue about the rental car"],
        "emotional_arc": "mild tension during conversation",
        "context_tags": ["rental car", "living room"],
        "activity_description": "Living room conversation about rental car.",
    }


def test_analyze_scene_context_llm_uses_low_signal_fallback_without_call(monkeypatch) -> None:
    called = {"value": False}

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["value"] = True
        raise AssertionError("requests.post should not be called for low-signal scenes")

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 9,
            "start": 120.0,
            "end": 123.0,
            "caption": "a black background with a white and red light",
            "transcript": "",
            "objects": [],
            "face_count": 0,
            "emotions": [],
            "speakers": [],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    assert called["value"] is False
    assert result == {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "low-signal scene",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }


def test_analyze_scene_context_llm_uses_monologue_fallback_for_low_signal_transcript(monkeypatch) -> None:
    called = {"value": False}

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["value"] = True
        raise AssertionError("requests.post should not be called for low-signal monologue scenes")

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 1,
            "start": 0.0,
            "end": 8.0,
            "caption": "a black background with a white and red light",
            "transcript": "You ever put on a bathing suit that you don't even know exactly where you are inside?",
            "objects": [],
            "face_count": 0,
            "emotions": [],
            "speakers": [],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    assert called["value"] is False
    assert result == {
        "narrative_summary": "Spoken monologue about bathing suit.",
        "key_moments": ["Speaker delivers a monologue about bathing suit"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", "bathing suit"],
        "activity_description": "Spoken monologue about bathing suit.",
    }


def test_analyze_scene_context_llm_uses_stage_monologue_fallback(monkeypatch) -> None:
    called = {"value": False}

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["value"] = True
        raise AssertionError("requests.post should not be called for stage monologue scenes")

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 0,
            "start": 0.0,
            "end": 30.0,
            "caption": "a man in a brown jacket is holding a microphone",
            "transcript": (
                "Can you give me an explanation as to why the pharmacist has to be two and a half feet up "
                "above everybody else? Look out everybody, I'm working with pills."
            ),
            "objects": [{"label": "person"}, {"label": "cell phone"}],
            "face_count": 1,
            "emotions": [{"label": "surprise", "score": 0.6}],
            "speakers": ["SPEAKER_00"],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    assert called["value"] is False
    assert result == {
        "narrative_summary": "Spoken monologue about pharmacist.",
        "key_moments": ["Speaker delivers a monologue about pharmacist"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", "pharmacist"],
        "activity_description": "Spoken monologue about pharmacist.",
    }


def test_analyze_scene_context_llm_uses_minimal_fallback_for_stage_oh_scene(monkeypatch) -> None:
    called = {"value": False}

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        called["value"] = True
        raise AssertionError("requests.post should not be called for minimal stage scenes")

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 37,
            "start": 800.0,
            "end": 804.0,
            "caption": "a man in a suit and tie standing on a stage",
            "transcript": "Oh",
            "objects": [],
            "face_count": 0,
            "emotions": [{"label": "neutral", "score": 0.5}],
            "speakers": [],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    assert called["value"] is False
    assert result == {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "low-signal scene",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }


def test_normalize_scene_context_payload_filters_generic_tags_and_promotes_topics() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A group of people are talking in a living room about renting a car.",
            "key_moments": ["People greet each other indoors", "They argue about the rental car"],
            "emotional_arc": "mild tension during conversation",
            "context_tags": ["indoor conversation", "living room", "woman", "man"],
            "activity_description": "People talk indoors about travel and a rental car.",
        },
        {
            "caption": "a woman standing in a living room with a man",
            "transcript": "How much is a rental car? Put on the air conditioning. We are in Florida.",
            "objects": [{"label": "person"}],
        },
    )

    assert result == {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["People greet each other indoors", "They argue about the rental car"],
        "emotional_arc": "mild tension during conversation",
        "context_tags": ["living room", "rental car", "air conditioning", "florida"],
        "activity_description": "Living room conversation about rental car.",
    }


def test_extract_transcript_topic_hints_suppresses_low_value_fragments() -> None:
    assert analyzer._extract_transcript_topic_hints("Are you people aware? There must be some mistake.") == []
    assert analyzer._extract_transcript_topic_hints(
        "My capillaries burst and the pressure on my mask was terrible."
    ) == ["mask", "capillaries"]
    assert analyzer._extract_transcript_topic_hints(
        "Is it the white shoes? Isn't he supposed to be the emcee? What about those muscle relaxers?"
    ) == ["emcee", "white shoes", "muscle relaxers"]
    assert analyzer._extract_transcript_topic_hints(
        "Can you give me an explanation as to why the pharmacist has to be two and a half feet up? "
        "Look out everybody, I'm working with pills."
    ) == ["pharmacist", "pills"]
    assert analyzer._extract_transcript_topic_hints(
        "Hello, Miss Pepper. It's a pleasure to meet you and you must be Professor von Nostrand. "
        "I've read your book about Shakespeare."
    ) == ["miss pepper", "professor von nostrand", "shakespeare"]


def test_normalize_scene_context_payload_drops_unsupported_setting_tags() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Three men discuss a gift they received while writing in bed.",
            "key_moments": ["One man offers a pen", "The others resist taking it"],
            "emotional_arc": "mild tension",
            "context_tags": ["kitchen", "bedroom", "pen"],
            "activity_description": "Three men discuss a gift while writing in bed.",
        },
        {
            "caption": "the three men are talking in a kitchen",
            "transcript": "That was a gift. A lot of times I write in bed. Take the pen.",
            "objects": [{"label": "person"}],
        },
    )

    assert result == {
        "narrative_summary": "Three men discuss a gift they received while writing in bed.",
        "key_moments": ["One man offers a pen", "The others resist taking it"],
        "emotional_arc": "mild tension",
        "context_tags": ["kitchen", "pen"],
        "activity_description": "Three men discuss a gift while writing in bed.",
    }


def test_normalize_scene_context_payload_rewrites_unsupported_social_roles_and_weak_visible_focus() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A group of friends gather around a couch to discuss their plans.",
            "key_moments": [
                "The friends sit on the couch together",
                "They look at the microwave",
            ],
            "emotional_arc": "tense discussion",
            "context_tags": ["couch", "microwave", "lawyer", "case"],
            "activity_description": "The couple looks at the microwave while sitting on the couch.",
        },
        {
            "caption": "a man and woman sitting on a couch",
            "transcript": "Has Morty decided on a lawyer yet? Jack has no case.",
            "objects": [{"label": "person"}, {"label": "microwave"}],
        },
    )

    assert result == {
        "narrative_summary": "Couch conversation about lawyer.",
        "key_moments": ["They mention lawyer."],
        "emotional_arc": "tense discussion",
        "context_tags": ["couch", "lawyer", "case"],
        "activity_description": "Couch conversation about lawyer.",
    }


def test_normalize_scene_context_payload_keeps_transcript_supported_social_roles() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Friends talk in the kitchen about the condo.",
            "key_moments": ["Friends talk in the kitchen", "They discuss the condo rules"],
            "emotional_arc": "mild tension",
            "context_tags": ["friends", "kitchen", "condo"],
            "activity_description": "Friends gather in the kitchen to discuss the condo.",
        },
        {
            "caption": "three people are talking in a kitchen",
            "transcript": "Why do you need more friends? You've got plenty of friends. What about the condo?",
            "objects": [{"label": "person"}],
        },
    )

    assert result == {
        "narrative_summary": "Friends talk in the kitchen about the condo.",
        "key_moments": ["Friends talk in the kitchen", "They discuss the condo rules"],
        "emotional_arc": "mild tension",
        "context_tags": ["kitchen", "condo"],
        "activity_description": "Friends gather in the kitchen to discuss the condo.",
    }


def test_normalize_scene_context_payload_rewrites_unsupported_waiting_and_arrival_language() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Two women wait indoors for someone to arrive.",
            "key_moments": ["They wait for someone to arrive"],
            "emotional_arc": "sadness and anticipation",
            "context_tags": ["waiting for someone", "rental car", "florida"],
            "activity_description": "Two women wait indoors for someone to arrive.",
        },
        {
            "caption": "two women are standing in a room with a blue backpack",
            "transcript": "Welcome to Florida. We waited 35 minutes in the rental car place.",
            "objects": [{"label": "person"}, {"label": "backpack"}],
        },
    )

    assert result == {
        "narrative_summary": "Conversation about rental car.",
        "key_moments": ["They mention rental car."],
        "emotional_arc": "sadness and anticipation",
        "context_tags": ["rental car", "florida"],
        "activity_description": "Conversation about rental car.",
    }


def test_normalize_scene_context_payload_rewrites_unsupported_role_language_in_emotional_arc() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Table conversation about pen.",
            "key_moments": ["The men sit at a table", "They talk about peanuts and scotch"],
            "emotional_arc": "Neutral conversation between friends",
            "context_tags": ["table", "pen"],
            "activity_description": "Table conversation about pen.",
        },
        {
            "caption": "people sitting at a table",
            "transcript": "Have you ever noticed how they always give you the peanuts on the plane? All I said was I liked the pen!",
            "objects": [{"label": "person"}, {"label": "table"}],
        },
    )

    assert result == {
        "narrative_summary": "Table conversation about pen.",
        "key_moments": ["The men sit at a table", "They talk about peanuts and scotch"],
        "emotional_arc": "Neutral conversation",
        "context_tags": ["table", "pen"],
        "activity_description": "Table conversation about pen.",
    }
