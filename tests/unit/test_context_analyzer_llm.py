from __future__ import annotations

from typing import Any

from steps.common import context_analyzer_llm as analyzer


def _assert_context_payload(
    result: dict[str, Any] | None,
    expected: dict[str, Any],
    *,
    primary_tags: list[str] | None = None,
    contextual_tags: list[str] | None = None,
    structural_tags: list[str] | None = None,
) -> None:
    assert result is not None
    assert result["narrative_summary"] == expected["narrative_summary"]
    assert result["key_moments"] == expected["key_moments"]
    assert result["emotional_arc"] == expected["emotional_arc"]
    assert result["context_tags"] == expected["context_tags"]
    assert result["activity_description"] == expected["activity_description"]
    assert "primary_tags" in result
    assert "contextual_tags" in result
    assert "structural_tags" in result
    if primary_tags is not None:
        assert result["primary_tags"] == primary_tags
    if contextual_tags is not None:
        assert result["contextual_tags"] == contextual_tags
    if structural_tags is not None:
        assert result["structural_tags"] == structural_tags


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

    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["They mention rental car.", "They argue about the rental car"],
        "emotional_arc": "mild tension during conversation",
        "context_tags": ["rental car", "living room"],
        "activity_description": "Living room conversation about rental car.",
    }, primary_tags=["rental car"], contextual_tags=["living room"], structural_tags=[])


def test_analyze_scene_context_llm_uses_grounded_fallback_for_bad_llm_json(monkeypatch) -> None:
    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "not json"}}]}

    def _fake_post(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _Response()

    monkeypatch.setattr(analyzer.requests, "post", _fake_post)

    result = analyzer.analyze_scene_context_llm(
        {
            "index": 4,
            "start": 126.0,
            "end": 154.0,
            "caption": "two people are talking in a living room",
            "transcript": "How much is the rental car? Twenty-five bucks a day.",
            "objects": [{"label": "person"}],
            "face_count": 0,
            "emotions": [{"label": "neutral", "score": 0.7}],
            "speakers": ["SPEAKER_00"],
        },
        {"llm": {"api_url": "http://localhost:38005/v1/chat/completions", "timeout": 12}},
    )

    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["They mention rental car."],
        "emotional_arc": "neutral audio emotion signal",
        "context_tags": ["rental car", "living room"],
        "activity_description": "Living room conversation about rental car.",
    }, primary_tags=["rental car"], contextual_tags=["living room"], structural_tags=[])


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
    _assert_context_payload(result, {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "low-signal scene",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["low-signal scene"])


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
    _assert_context_payload(result, {
        "narrative_summary": "Spoken monologue about bathing suit.",
        "key_moments": ["Speaker delivers a monologue about bathing suit"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", "bathing suit"],
        "activity_description": "Spoken monologue about bathing suit.",
    }, primary_tags=["bathing suit"], contextual_tags=[], structural_tags=["spoken monologue"])


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
    _assert_context_payload(result, {
        "narrative_summary": "Spoken monologue about pharmacist.",
        "key_moments": ["Speaker delivers a monologue about pharmacist"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue", "pharmacist"],
        "activity_description": "Spoken monologue about pharmacist.",
    }, primary_tags=["pharmacist"], contextual_tags=[], structural_tags=["spoken monologue"])


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
    _assert_context_payload(result, {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "low-signal scene",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["low-signal scene"])


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

    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["They mention rental car.", "They argue about the rental car"],
        "emotional_arc": "mild tension during conversation",
        "context_tags": ["rental car", "living room", "air conditioning", "florida"],
        "activity_description": "Living room conversation about rental car.",
    }, primary_tags=["rental car"], contextual_tags=["living room", "air conditioning", "florida"], structural_tags=[])


def test_extract_transcript_topic_hints_suppresses_low_value_fragments() -> None:
    assert analyzer._extract_transcript_topic_hints("Are you people aware? There must be some mistake.") == []
    assert analyzer._extract_transcript_topic_hints(
        "He's this guy in the neighborhood. Parks cars on the block. "
        "The whole block. 40, 50 cars."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "So, I was in the drugstore the other day trying to get a cold medication. "
        "First of all, they always show you the human body."
    ) == ["cold medication", "drugstore"]
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
    assert analyzer._extract_transcript_topic_hints(
        "Maybe you should go to Long Island. Thanks for the ride, George."
    ) == ["Long Island"]
    assert analyzer._extract_transcript_topic_hints(
        "Anyway, thanks a lot for letting us stay here Steve. If you're ever in the city, come to a comedy club."
    ) == ["Steve"]
    assert analyzer._extract_transcript_topic_hints(
        "Mr. Pocotillo! Do I know you? This is the kind of lasting impression I make on people."
    ) == ["Steve Pocatillo"]
    assert analyzer._extract_transcript_topic_hints(
        "Ask Mark. Mark, is this true?"
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "Maybe Kramer can come pick us up."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "We made a reservation for dinner."
    ) == ["reservation"]
    assert analyzer._extract_transcript_topic_hints(
        "Do you have a question? Sure."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "The blue Ford Escort is parked outside."
    ) == ["Ford Escort"]
    assert analyzer._extract_transcript_topic_hints(
        "Jerry Baby says we should watch cable station lov."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "He moves them from one side of the street to the other so you don't get a ticket."
    ) == ["alternate side"]
    assert analyzer._extract_transcript_topic_hints(
        "That's my rent-a-car. What happened to the car?"
    ) == ["rental car"]
    assert analyzer._extract_transcript_topic_hints(
        "It's a different interpretation. No job. Pocketing cars."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "This is the kind of lasting impression I make on people."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "Go off oppression. Wild oppression. Don't."
    ) == []
    assert analyzer._extract_transcript_topic_hints(
        "the dentist appointment is tomorrow morning"
    ) == ["dentist appointment"]
    assert analyzer._extract_transcript_topic_hints(
        "This is our drug company, see the public. And he's always in like a certain pain."
    ) == ["drug company"]
    assert analyzer._extract_transcript_topic_hints(
        "Peanut brittle, peanut butter, peanut oil. I wonder what happened to my fiancé."
    ) == ["peanut"]


    assert analyzer._extract_transcript_topic_hints(
        "These pretzels are making me thirsty. Do you know anything about this pretzel guy?"
    ) == ["pretzel"]


def test_spoken_monologue_payload_without_topic_avoids_spoken_topic_fallback() -> None:
    result = analyzer._spoken_monologue_payload([])  # type: ignore[attr-defined]
    _assert_context_payload(result, {
        "narrative_summary": "Spoken monologue.",
        "key_moments": ["Speaker delivers a monologue"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue"],
        "activity_description": "Spoken monologue.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["spoken monologue"])


def test_transcript_grounded_topic_candidate_accepts_explicit_pattern_aliases() -> None:
    assert analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
        "Steve Pocatillo",
        "Who is it? Mr. Pocotillo! You mean you don't recognize my voice?",
    )
    assert analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
        "alternate side",
        "He moves them from one side of the street to the other so you don't get a ticket.",
    )
    assert analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
        "rental car",
        "That's my rent-a-car. What happened to the car?",
    )


def test_rewrite_key_moment_prefers_topic_when_moment_is_not_transcript_grounded() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "The woman nods while he looks at her.",
        transcript="The address was 8713 Riviera Drive near the Long Island Expressway.",
        evidence_blob="the address was 8713 riviera drive near the long island expressway a man in a white robe is standing in front of a woman person person",
        setting_hint=None,
        topic_hint="Long Island Expressway",
    )

    assert rewritten == "They mention Long Island Expressway."


def test_rewrite_scene_text_upgrades_setting_only_conversation_with_transcript_topic() -> None:
    rewritten = analyzer._rewrite_scene_text(  # type: ignore[attr-defined]
        "Kitchen conversation.",
        setting_hint="kitchen",
        topic_hint="Steve",
        force_rewrite=False,
    )

    assert rewritten == "Kitchen conversation about Steve."


def test_rewrite_scene_text_upgrades_minimal_scene_when_transcript_topic_exists() -> None:
    rewritten = analyzer._rewrite_scene_text(  # type: ignore[attr-defined]
        "Minimal visual or dialogue content.",
        setting_hint=None,
        topic_hint="Steve Pocatillo",
        force_rewrite=False,
    )

    assert rewritten == "Conversation about Steve Pocatillo."


def test_rewrite_key_moment_flattens_other_man_question_into_setting_conversation() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "The other man asks if they have any plans for the weekend",
        transcript="He's this guy in the neighborhood. Parks cars on the block.",
        evidence_blob="he's this guy in the neighborhood parks cars on the block two men in a kitchen talking to each other man person person refrigerator microwave",
        setting_hint="kitchen",
        topic_hint=None,
    )

    assert rewritten == "Kitchen conversation."


def test_rewrite_key_moment_flattens_ungrounded_weekend_claim_into_setting_conversation() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "He begins to describe his plans for the weekend",
        transcript="He's this guy in the neighborhood. Parks cars on the block.",
        evidence_blob="he's this guy in the neighborhood parks cars on the block two men in a kitchen talking to each other man person person refrigerator microwave",
        setting_hint="kitchen",
        topic_hint=None,
    )

    assert rewritten == "Kitchen conversation."


def test_rewrite_key_moment_drops_ungrounded_visual_action_without_topic_or_setting() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "He looks at the clock on the wall",
        transcript=(
            "I went down to visit my sister in Virginia next Wednesday for a week, "
            "so I can't park it."
        ),
        evidence_blob=(
            "i went down to visit my sister in virginia next wednesday for a week "
            "so i can't park it a man sitting at a desk person dining table chair"
        ),
        setting_hint=None,
        topic_hint=None,
    )

    assert rewritten is None


def test_rewrite_key_moment_drops_low_value_visual_staging_without_topic_or_setting() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "The man sits in a chair with a glass",
        transcript=(
            "Whoo! Hey. Do you know any women we could call? "
            "I got a girl in the next building."
        ),
        evidence_blob=(
            "whoo hey do you know any women we could call i got a girl in the next building "
            "a man sitting in a chair with a glass person wine glass"
        ),
        setting_hint=None,
        topic_hint=None,
    )

    assert rewritten is None


def test_rewrite_key_moment_drops_generic_pronoun_action_without_topic_or_setting() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "He talks to someone else",
        transcript=(
            "Whoo! Hey. Do you know any women we could call? "
            "I got a girl in the next building."
        ),
        evidence_blob=(
            "whoo hey do you know any women we could call i got a girl in the next building "
            "a man sitting in a chair with a glass person wine glass"
        ),
        setting_hint=None,
        topic_hint=None,
    )

    assert rewritten is None


def test_rewrite_key_moment_drops_ordinal_role_narration_without_topic_or_setting() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "The first man says they're not sure who he recognizes",
        transcript=(
            "Who is it? Jerry Baby! Do I know you? "
            "This is the kind of lasting impression I make on people."
        ),
        evidence_blob=(
            "who is it jerry baby do i know you this is the kind of lasting impression i make on people "
            "two men in suits are talking in a room person tie"
        ),
        setting_hint=None,
        topic_hint=None,
    )

    assert rewritten is None


def test_rewrite_key_moment_flattens_ungrounded_pronoun_question_into_topic() -> None:
    rewritten = analyzer._rewrite_key_moment(  # type: ignore[attr-defined]
        "She looks confused and asks why he is there",
        transcript=(
            "Maybe you should take a look at a train schedule. "
            "I knew the exit on the Long Island Expressway."
        ),
        evidence_blob=(
            "maybe you should take a look at a train schedule i knew the exit on the long island expressway "
            "a man in a white robe is standing in front of a woman person person"
        ),
        setting_hint=None,
        topic_hint="Long Island Expressway",
    )

    assert rewritten == "They mention Long Island Expressway."


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

    _assert_context_payload(result, {
        "narrative_summary": "Kitchen conversation about pen.",
        "key_moments": ["One man offers a pen", "They mention pen."],
        "emotional_arc": "mild tension",
        "context_tags": ["pen", "kitchen"],
        "activity_description": "Kitchen conversation about pen.",
    }, primary_tags=["pen"], contextual_tags=["kitchen"], structural_tags=[])


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

    _assert_context_payload(result, {
        "narrative_summary": "Couch conversation about lawyer.",
        "key_moments": ["They mention lawyer."],
        "emotional_arc": "tense discussion",
        "context_tags": ["lawyer", "couch", "case"],
        "activity_description": "Couch conversation about lawyer.",
    }, primary_tags=["lawyer"], contextual_tags=["couch", "case"], structural_tags=[])


def test_normalize_scene_context_payload_rewrites_coworker_plans_language_to_grounded_topic() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A group of coworkers discuss their plans for the day.",
            "key_moments": ["They mention attention yeah."],
            "emotional_arc": "Neutral tone between coworkers",
            "context_tags": ["attention yeah"],
            "activity_description": "The coworkers engage in informal discussions about their day's tasks and plans.",
        },
        {
            "caption": "person and person in the office",
            "transcript": (
                "Well, if not now, when? Give me a half hour. Okay, half hour. "
                "Peanut brittle, peanut butter, peanut oil. "
                "I wonder what happened to my fiancé."
            ),
            "objects": [{"label": "person"}, {"label": "wine glass"}, {"label": "cup"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about peanut.",
        "key_moments": ["They mention peanut."],
        "emotional_arc": "Neutral tone between coworkers",
        "context_tags": ["peanut"],
        "activity_description": "Conversation about peanut.",
    })


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

    _assert_context_payload(result, {
        "narrative_summary": "Friends talk in the kitchen about the condo.",
        "key_moments": ["Friends talk in the kitchen", "They mention condo."],
        "emotional_arc": "mild tension",
        "context_tags": ["condo", "kitchen"],
        "activity_description": "Friends gather in the kitchen to discuss the condo.",
    }, primary_tags=["condo"], contextual_tags=["kitchen"], structural_tags=[])


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

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about rental car.",
        "key_moments": ["They mention rental car."],
        "emotional_arc": "sadness and anticipation",
        "context_tags": ["rental car", "florida"],
        "activity_description": "Conversation about rental car.",
    })


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

    _assert_context_payload(result, {
        "narrative_summary": "Table conversation about pen.",
        "key_moments": ["They mention pen.", "They talk about peanuts and scotch"],
        "emotional_arc": "Neutral conversation",
        "context_tags": ["pen"],
        "activity_description": "Table conversation about pen.",
    }, primary_tags=["pen"], contextual_tags=[], structural_tags=["table"])


def test_normalize_scene_context_payload_drops_low_value_human_category_tags() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Two men in a store discuss their medical bills and belongings stolen from them.",
            "key_moments": ["The men stand in the store", "They talk about the stolen money"],
            "emotional_arc": "urgent disagreement",
            "context_tags": ["store", "men in a store", "person", "medical bills"],
            "activity_description": "Two men in a store discuss their medical bills and belongings stolen from them.",
        },
        {
            "caption": "two men are standing in a store",
            "transcript": "They owe me ten dollars. Why are you treating me to medicine?",
            "objects": [{"label": "person"}, {"label": "store"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Store conversation about medicine.",
        "key_moments": ["They mention medicine."],
        "emotional_arc": "urgent disagreement",
        "context_tags": ["medicine", "store"],
        "activity_description": "Store conversation about medicine.",
    }, primary_tags=["medicine"], contextual_tags=["store"], structural_tags=[])


def test_normalize_scene_context_payload_rewrites_low_value_gendered_visual_phrasing() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A man and woman sit on a couch talking about Woody Allen.",
            "key_moments": ["The man and woman sit on the couch", "They mention Woody Allen"],
            "emotional_arc": "neutral discussion",
            "context_tags": ["man and woman", "couch", "Woody Allen"],
            "activity_description": "A man and woman sit on a couch discussing Woody Allen.",
        },
        {
            "caption": "a man and woman sitting on a couch",
            "transcript": "Did you hear what Woody Allen said about the movie?",
            "objects": [{"label": "person"}, {"label": "couch"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Couch conversation about Woody Allen.",
        "key_moments": ["They mention Woody Allen."],
        "emotional_arc": "neutral discussion",
        "context_tags": ["Woody Allen", "couch"],
        "activity_description": "Couch conversation about Woody Allen.",
    }, primary_tags=["Woody Allen"], contextual_tags=["couch"], structural_tags=[])


def test_normalize_scene_context_payload_flattens_gendered_emotional_arc_filler() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about Long Island Expressway.",
            "key_moments": ["They mention Long Island Expressway."],
            "emotional_arc": "Neutral tone between the man and the woman",
            "context_tags": ["Long Island Expressway", "Long Island"],
            "activity_description": "Conversation about Long Island Expressway.",
        },
        {
            "caption": "a man in a white robe is standing in front of a woman",
            "transcript": "I knew the exit on the Long Island Expressway.",
            "objects": [{"label": "person"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about Long Island Expressway.",
        "key_moments": ["They mention Long Island Expressway."],
        "emotional_arc": "neutral tone",
        "context_tags": ["Long Island Expressway", "Long Island"],
        "activity_description": "Conversation about Long Island Expressway.",
    })


def test_normalize_scene_context_payload_drops_generic_tags_once_specific_topic_is_present() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about Long Island Expressway.",
            "key_moments": ["They mention Long Island Expressway."],
            "emotional_arc": "neutral tone",
            "context_tags": ["man", "woman", "conversation", "man in white robe"],
            "activity_description": "Conversation about Long Island Expressway.",
        },
        {
            "caption": "a man in a white robe is standing in front of a woman",
            "transcript": "I knew the exit on the Long Island Expressway.",
            "objects": [{"label": "person"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about Long Island Expressway.",
        "key_moments": ["They mention Long Island Expressway."],
        "emotional_arc": "neutral tone",
        "context_tags": ["Long Island Expressway", "Long Island"],
        "activity_description": "Conversation about Long Island Expressway.",
    })


def test_normalize_scene_context_payload_drops_residual_low_value_tags() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Table conversation about reservation.",
            "key_moments": ["They mention reservation.", "The men sit at a table"],
            "emotional_arc": "neutral discussion",
            "context_tags": [
                "table",
                "reservation",
                "men sitting at a table",
                "glove compartment",
                "glove compartment wait",
                "attention yeah",
                "fianc‚",
                "transition phase",
                "move cars",
            ],
            "activity_description": "Table conversation about reservation.",
        },
        {
            "caption": "two men sitting at a table",
            "transcript": "I made a reservation. Check the glove compartment and wait.",
            "objects": [{"label": "person"}, {"label": "table"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Table conversation about reservation.",
        "key_moments": ["They mention reservation."],
        "emotional_arc": "neutral discussion",
        "context_tags": ["reservation"],
        "activity_description": "Table conversation about reservation.",
    }, primary_tags=["reservation"], contextual_tags=[], structural_tags=["table"])


def test_normalize_scene_context_payload_drops_caption_shaped_people_tags_and_mojibake() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Couch conversation.",
            "key_moments": ["Couch conversation.", "She talks to her fianc‚"],
            "emotional_arc": "anger and frustration",
            "context_tags": ["woman sitting on couch", "fianc‚", "vibrant woman", "blue shirt", "couch"],
            "activity_description": "Couch conversation.",
        },
        {
            "caption": "a woman sitting on a couch",
            "transcript": "",
            "objects": [{"label": "person"}, {"label": "couch"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Couch conversation.",
        "key_moments": ["Couch conversation."],
        "emotional_arc": "anger and frustration",
        "context_tags": ["couch"],
        "activity_description": "Couch conversation.",
    })


def test_normalize_scene_context_payload_clamps_caption_shaped_visual_narration_to_grounded_topic() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about Pendant Publishing.",
            "key_moments": ["The woman reads a manuscript", "The man drives a car"],
            "emotional_arc": "neutral discussion",
            "context_tags": ["Woman reading manuscript", "Pendant Publishing"],
            "activity_description": "Conversation about Pendant Publishing.",
        },
        {
            "caption": "a woman in a brown jacket and a man in a blue shirt",
            "transcript": "Right now I'm reading manuscripts for Pendant Publishing.",
            "objects": [{"label": "person"}, {"label": "car"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about Pendant Publishing.",
        "key_moments": ["They mention Pendant Publishing."],
        "emotional_arc": "neutral discussion",
        "context_tags": ["Pendant Publishing"],
        "activity_description": "Conversation about Pendant Publishing.",
    })


def test_normalize_scene_context_payload_rewrites_interpretive_summary_to_grounded_topic() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "The group discusses the Big Bang, its impact on humanity, and their current situation.",
            "key_moments": [
                "The speaker mentions the Big Bang",
                "They discuss the impact of the Big Bang on humanity",
                "The speaker asks if they should leave the area",
            ],
            "emotional_arc": "uneasy discussion",
            "context_tags": ["Big Bang", "Civil War"],
            "activity_description": "The group discusses the Big Bang, its impact on humanity, and their current situation.",
        },
        {
            "caption": "the big bang - the big bang - the big bang",
            "transcript": "Oh, you got the Civil War book. I saw some of that show.",
            "objects": [{"label": "person"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about Civil War.",
        "key_moments": ["They mention Civil War."],
        "emotional_arc": "uneasy discussion",
        "context_tags": ["Civil War"],
        "activity_description": "Conversation about Civil War.",
    })


def test_normalize_scene_context_payload_drops_caption_shaped_visual_action_without_topic() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Minimal visual or dialogue content.",
            "key_moments": ["He eats lunch on a dining table"],
            "emotional_arc": "neutral tone",
            "context_tags": ["desk", "dining table"],
            "activity_description": "Minimal visual or dialogue content.",
        },
        {
            "caption": "a man sitting at a desk",
            "transcript": "I'm in a transition phase right now.",
            "objects": [{"label": "person"}, {"label": "desk"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content."],
        "emotional_arc": "neutral tone",
        "context_tags": [],
        "activity_description": "Minimal visual or dialogue content.",
    })


def test_normalize_scene_context_payload_collapses_low_value_transcript_garbage_to_minimal() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about go off oppression.",
            "key_moments": ["They mention go off oppression."],
            "emotional_arc": "mild tension during conversation",
            "context_tags": [
                "go off oppression",
                "off oppression wild",
                "oppression wild oppression",
            ],
            "activity_description": "Conversation about go off oppression.",
        },
        {
            "caption": "",
            "transcript": "Go off oppression. Wild oppression. Don't.",
            "objects": [{"label": "person"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content."],
        "emotional_arc": "mild tension during conversation",
        "context_tags": [],
        "activity_description": "Minimal visual or dialogue content.",
    })


def test_normalize_scene_context_payload_drops_descriptive_visual_support_tag_when_topic_wins() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Kitchen conversation about Owen March.",
            "key_moments": ["They mention Owen March."],
            "emotional_arc": "Neutral tone throughout the scene",
            "context_tags": ["Man with a limp", "Owen March", "Upper West Side"],
            "activity_description": "Kitchen conversation about Owen March.",
        },
        {
            "caption": "a man standing in a kitchen",
            "transcript": "Owen March is up on the Upper West Side.",
            "objects": [{"label": "person"}, {"label": "kitchen"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Kitchen conversation about Owen March.",
        "key_moments": ["They mention Owen March."],
        "emotional_arc": "Neutral tone throughout the scene",
        "context_tags": ["Owen March", "Upper West Side"],
        "activity_description": "Kitchen conversation about Owen March.",
    })


def test_normalize_scene_context_payload_does_not_promote_low_value_object_tags() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Table conversation.",
            "key_moments": ["Table conversation."],
            "emotional_arc": "neutral tone",
            "context_tags": ["potted plant", "wine glass"],
            "activity_description": "Table conversation.",
        },
        {
            "caption": "a table with a potted plant and a wine glass",
            "transcript": "",
            "objects": [{"label": "table"}, {"label": "potted plant"}, {"label": "wine glass"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Table conversation.",
        "key_moments": ["Table conversation."],
        "emotional_arc": "neutral tone",
        "context_tags": [],
        "activity_description": "Table conversation.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["potted plant", "wine glass"])


def test_normalize_scene_context_payload_keeps_contextual_setting_but_contains_sitting_as_structural() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Living room conversation.",
            "key_moments": ["Living room conversation."],
            "emotional_arc": "neutral tone",
            "context_tags": ["living room", "couch", "sitting"],
            "activity_description": "Living room conversation.",
        },
        {
            "caption": "a person sitting on a couch in a living room",
            "transcript": "",
            "objects": [{"label": "person"}, {"label": "couch"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation.",
        "key_moments": ["Living room conversation."],
        "emotional_arc": "neutral tone",
        "context_tags": ["living room", "couch"],
        "activity_description": "Living room conversation.",
    }, primary_tags=[], contextual_tags=["living room", "couch"], structural_tags=["sitting"])
