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
            "ocr_text": "DEC 16 2002",
            "music_events": [{"label": "applause", "context": "APPLAUSE"}],
            "time_hints": {"explicit_dates": ["2002-12-16"], "months": ["december"]},
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
    assert "Visible text: DEC 16 2002" in user_prompt
    assert "Audio/music events: applause, APPLAUSE" in user_prompt
    assert "Time hints: 2002-12-16, december" in user_prompt
    assert "Transcript excerpt:" in user_prompt
    assert "Transcript topic hints:" in user_prompt
    assert "Audio emotion signal:" in user_prompt
    assert "Topic hints are incomplete literal excerpts" in user_prompt
    assert 'Minimal visual or dialogue content.' in user_prompt
    assert "- relationships:" not in user_prompt
    assert '"relationships"' not in user_prompt
    assert 'context_tags: an array of 0-4 short evidence-backed tags; use [] when unsupported' in user_prompt
    assert 'or "unqualified" when scene mood is not established' in user_prompt


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

    class Client:
        last_model_used = None
        last_provider_used = None

        def chat(self, **kwargs):
            captured["payload"] = kwargs
            return _Response().json()

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
        llm_client=Client(),
    )

    assert result["status"] == "ok"
    assert result["source"] == "scene_context_llm"
    assert result["reason"] == "model_output"
    assert captured["payload"]["temperature"] == 0.1

    system_prompt = captured["payload"]["messages"][0]["content"]
    user_prompt = captured["payload"]["messages"][1]["content"]
    assert "EVIDENCE PRIORITY (STRICT)" in system_prompt
    assert "Do not infer family roles, friendships, marriages, jobs, or social relationships" in system_prompt
    assert "Do not use interpretive verbs like waiting, discussing, thinking, feeling, planning, or arguing" in system_prompt
    assert "- relationships:" not in user_prompt
    assert '"relationships"' not in user_prompt
    assert "Transcript topic hints:" in user_prompt
    assert "Topic hints are incomplete literal excerpts" in user_prompt
    assert "Return ONLY a JSON object with exactly these keys" in user_prompt

    assert result["emotion_qualification"]["status"] == "unqualified"
    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation about rental car.",
        "key_moments": ["They mention rental car.", "They argue about the rental car"],
        "emotional_arc": "unqualified",
        "context_tags": ["rental car", "living room"],
        "activity_description": "Living room conversation about rental car.",
    }, primary_tags=["rental car"], contextual_tags=["living room"], structural_tags=[])


def test_analyze_scene_context_llm_uses_grounded_fallback_for_bad_llm_json(monkeypatch) -> None:
    class _Response:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": "not json"}}]}

    class Client:
        def chat(self, **_kwargs):
            return _Response().json()

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
        llm_client=Client(),
    )

    assert result["emotion_qualification"]["status"] == "unqualified"
    _assert_context_payload(result, {
        "narrative_summary": "Living room conversation.",
        "key_moments": ["Living room conversation."],
        "emotional_arc": "unqualified",
        "context_tags": ["living room"],
        "activity_description": "Living room conversation.",
    }, primary_tags=[], contextual_tags=["living room"], structural_tags=[])


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
    assert result["status"] == "not_applicable"
    assert result["source"] == "scene_context_heuristic"
    assert result["reason"] == "low_signal"
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
        "narrative_summary": "Spoken monologue.",
        "key_moments": ["Speaker delivers a monologue"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue"],
        "activity_description": "Spoken monologue.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["spoken monologue"])


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
    assert result["emotion_qualification"]["status"] == "unqualified"
    _assert_context_payload(result, {
        "narrative_summary": "Spoken monologue.",
        "key_moments": ["Speaker delivers a monologue"],
        "emotional_arc": "unqualified",
        "context_tags": ["spoken monologue"],
        "activity_description": "Spoken monologue.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["spoken monologue"])


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
    assert result["emotion_qualification"]["status"] == "unqualified"
    _assert_context_payload(result, {
        "narrative_summary": "Minimal visual or dialogue content.",
        "key_moments": ["Minimal visual or dialogue content"],
        "emotional_arc": "unqualified",
        "context_tags": ["low-signal scene"],
        "activity_description": "Minimal visual or dialogue content.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["low-signal scene"])


def test_normalize_scene_context_payload_filters_generic_tags_and_promotes_topics() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A group of people are talking in a living room about renting a car.",
            "key_moments": ["People greet each other indoors", "They argue about the rental car"],
            "emotional_arc": "mild tension during conversation",
            "context_tags": ["rental car", "living room", "air conditioning", "florida", "woman", "man"],
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


def test_normalize_scene_context_payload_promotes_grounded_activity_over_minimal_summary() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Minimal visual or dialogue content.",
            "key_moments": ["Minimal visual or dialogue content."],
            "emotional_arc": "Positive emotions as she performs and receives applause",
            "context_tags": ["applause"],
            "activity_description": "A girl plays the trumpet in a room, receiving applause from others.",
        },
        {
            "caption": "a girl playing a trumpet in a room",
            "transcript": "Thank you. Thank you very much. APPLAUSE",
            "objects": [{"label": "person"}],
            "ocr_text": "DEC 16 2002",
            "music_events": [{"label": "applause", "context": "APPLAUSE"}],
            "time_hints": {"explicit_dates": ["2002-12-16"], "months": ["december"]},
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "A girl plays the trumpet in a room, receiving applause from others.",
        "key_moments": ["A girl plays the trumpet in a room, receiving applause from others."],
        "emotional_arc": "Positive emotions as she performs and receives applause",
        "context_tags": ["applause"],
        "activity_description": "A girl plays the trumpet in a room, receiving applause from others.",
    }, primary_tags=[], contextual_tags=["applause"], structural_tags=[])


def test_normalize_scene_context_payload_drops_grounded_fragment_residue() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about convertible sofa.",
            "key_moments": [
                "The man sleeps on the convertible sofa",
                "The speaker talks about his back problems",
            ],
            "emotional_arc": "calm tone as the man sleeps",
            "context_tags": ["convertible sofa", "negotiating negotiation", "business leave"],
            "activity_description": "Conversation about convertible sofa.",
        },
        {
            "caption": "a man and woman sitting at a table",
            "transcript": (
                "You know, I never had a back problem until that night I slept on the convertible sofa. "
                "Now listen to me. I'm negotiating. Negotiation. This is what you do in business. "
                "Leave all my stuff here? Leave it."
            ),
            "objects": [{"label": "person"}, {"label": "dining table"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about convertible sofa.",
        "key_moments": [
            "The man sleeps on the convertible sofa",
            "The speaker talks about his back problems",
        ],
        "emotional_arc": "calm tone as the man sleeps",
        "context_tags": ["convertible sofa"],
        "activity_description": "Conversation about convertible sofa.",
    }, primary_tags=["convertible sofa"], contextual_tags=[], structural_tags=[])


def test_normalize_scene_context_payload_keeps_grounded_domain_topic() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Table conversation about clothing business.",
            "key_moments": [
                "They mention clothing business.",
                "She speaks about the new clothing design",
            ],
            "emotional_arc": "Surprised and excited",
            "context_tags": ["clothing business", "designer", "new look"],
            "activity_description": "Table conversation about clothing business.",
        },
        {
            "caption": "people sitting at a restaurant table",
            "transcript": (
                "You know that Leslie's in the clothing business? She's a designer. "
                "She's come up with a new one that's gonna be the big new look in men's fashions."
            ),
            "objects": [{"label": "person"}, {"label": "dining table"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Table conversation about clothing business.",
        "key_moments": [
            "They mention clothing business.",
            "She speaks about the new clothing design",
        ],
        "emotional_arc": "Surprised and excited",
        "context_tags": ["clothing business", "designer", "new look"],
        "activity_description": "Table conversation about clothing business.",
    }, primary_tags=["clothing business"], contextual_tags=["designer", "new look"], structural_tags=[])


def test_normalize_scene_context_payload_keeps_literal_business_topic_without_plot_expansion() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about business end.",
            "key_moments": [
                "They mention business end.",
                "The man accuses the woman of insubordination",
            ],
            "emotional_arc": "anger and frustration escalate as the argument intensifies",
            "context_tags": ["business end", "business deal"],
            "activity_description": "Conversation about business end.",
        },
        {
            "caption": "a man and woman in a dark room",
            "transcript": (
                "He was pretty emphatic. Pounded on his desk. I told you to take the offer. "
                "I'm not the creative guy. He handles the business end. "
                "Take a counter offer? How can I just cancel a whole deal?"
            ),
            "objects": [{"label": "person"}, {"label": "person"}],
        },
    )

    _assert_context_payload(result, {
        "narrative_summary": "Conversation about business end.",
        "key_moments": [
            "They mention business end.",
        ],
        "emotional_arc": "anger and frustration escalate as the argument intensifies",
        "context_tags": ["business end"],
        "activity_description": "Conversation about business end.",
    }, primary_tags=["business end"], contextual_tags=[], structural_tags=[])


def test_normalize_scene_context_payload_rejects_dangling_topic_without_inventing_a_label() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Conversation about position he was.",
            "key_moments": [
                "They mention position he was.",
                "Tie hangs from their hands",
            ],
            "emotional_arc": "Fear and disgust",
            "context_tags": ["position he was"],
            "activity_description": "Conversation about position he was.",
        },
        {
            "caption": "a man wearing a tie indoors",
            "transcript": (
                "Yes, he was not master of his domain. But how the muscles became so strained with overuse "
                "that eventually the hand locked into a deformed position. "
                "He was left with nothing but a claw. Traveled the world seeking a cure."
            ),
            "objects": [{"label": "person"}, {"label": "tie"}],
        },
    )

    # A dangling model fragment cannot authorize an invented medical label.
    assert "deformed hand" not in str(result).lower()
    assert "position he was" not in result["context_tags"]
    assert result["primary_tags"] == []


def test_extract_transcript_topic_hints_keeps_coherent_rehabilitation_phrase() -> None:
    assert analyzer._extract_transcript_topic_hints(
        "In the opinion of the board, you'd need further rehabilitation, I'm afraid."
    ) == ["further rehabilitation"]


def test_extract_transcript_topic_hints_are_literal_across_legacy_corpus() -> None:
    transcripts = [
        'Are you people aware? There must be some mistake.',
        "He's this guy in the neighborhood. Parks cars on the block. The whole block. 40, 50 cars.",
        'So, I was in the drugstore the other day trying to get a cold medication. First of all, they always show you the human body.',
        'My capillaries burst and the pressure on my mask was terrible.',
        "Is it the white shoes? Isn't he supposed to be the emcee? What about those muscle relaxers?",
        "Can you give me an explanation as to why the pharmacist has to be two and a half feet up? Look out everybody, I'm working with pills.",
        "Hello, Miss Pepper. It's a pleasure to meet you and you must be Professor von Nostrand. I've read your book about Shakespeare.",
        'Maybe you should go to Long Island. Thanks for the ride, George.',
        "Anyway, thanks a lot for letting us stay here Steve. If you're ever in the city, come to a comedy club.",
        'Mr. Pocotillo! Do I know you? This is the kind of lasting impression I make on people.',
        'Ask Mark. Mark, is this true?',
        'Maybe Kramer can come pick us up.',
        'We made a reservation for dinner.',
        'Do you have a question? Sure.',
        'The blue Ford Escort is parked outside.',
        'Jerry Baby says we should watch cable station lov.',
        "He moves them from one side of the street to the other so you don't get a ticket.",
        "That's my rent-a-car. What happened to the car?",
        "It's a different interpretation. No job. Pocketing cars.",
        'This is the kind of lasting impression I make on people.',
        "Go off oppression. Wild oppression. Don't.",
        'the dentist appointment is tomorrow morning',
        "This is our drug company, see the public. And he's always in like a certain pain.",
        'Peanut brittle, peanut butter, peanut oil. I wonder what happened to my fiancé.',
        "But to have a good pickle, you gotta understand the process. I don't understand this jewel that Jimmy Shar-",
        'The phone machine is like this relationship respirator keeping these marginal brain-dead relationships alive.',
        'It has a slight sing-songy quality.',
        'Operation Yeah. Yeah. Dr. Yeah.',
        'The thing about stand-up was, it always encouraged experimentation.',
        'Got a nice girl in a clean apartment. Yep. Just one little problem.',
        "Well, maybe she just wanted to move on to other business. No, no, this wasn't moving on.",
        "So what do you want me to do? I want restitution. Restitution? You want restitution? Why should I give you restitution? Because it's no good. Well, I got a perfect solution for you. Take your business elsewhere. I don't want your business.",
        'These pretzels are making me thirsty. Do you know anything about this pretzel guy?',
    ]
    for transcript in transcripts:
        hints = analyzer._extract_transcript_topic_hints(transcript)
        assert len(hints) <= 5
        assert len({hint.casefold() for hint in hints}) == len(hints)
        for hint in hints:
            assert analyzer._is_evidence_grounded_topic_candidate(hint, transcript)
    assert analyzer._extract_transcript_topic_hints("The blue Ford Escort is parked outside.") == ["Ford Escort"]
    assert analyzer._extract_transcript_topic_hints("the dentist appointment is tomorrow morning") == ["dentist appointment"]


def test_spoken_monologue_payload_without_topic_avoids_spoken_topic_fallback() -> None:
    result = analyzer._spoken_monologue_payload([])  # type: ignore[attr-defined]
    _assert_context_payload(result, {
        "narrative_summary": "Spoken monologue.",
        "key_moments": ["Speaker delivers a monologue"],
        "emotional_arc": "spoken performance",
        "context_tags": ["spoken monologue"],
        "activity_description": "Spoken monologue.",
    }, primary_tags=[], contextual_tags=[], structural_tags=["spoken monologue"])


def test_transcript_grounded_topic_candidate_rejects_unstated_plot_aliases() -> None:
    assert not analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
        "Steve Pocatillo",
        "Who is it? Mr. Pocotillo! You mean you don't recognize my voice?",
    )
    assert not analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
        "alternate side",
        "He moves them from one side of the street to the other so you don't get a ticket.",
    )
    assert not analyzer._is_transcript_grounded_topic_candidate(  # type: ignore[attr-defined]
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
    }, primary_tags=["lawyer"], contextual_tags=["couch", "case"], structural_tags=["microwave"])

    # Retain a detector candidate without turning it into a scene claim.
    assert "microwave" not in result["context_tags"]
    assert "microwave" not in result["narrative_summary"].lower()


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

    assert result["narrative_summary"].startswith('Transcript: "')
    assert "coworker" not in result["narrative_summary"].lower()
    assert "plans for the day" not in result["narrative_summary"].lower()
    assert result["context_tags"] == []


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
        "key_moments": ["Friends talk in the kitchen", "They discuss the condo rules"],
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
        "narrative_summary": "Store conversation.",
        "key_moments": ["Store conversation."],
        "emotional_arc": "urgent disagreement",
        "context_tags": ["store"],
        "activity_description": "Store conversation.",
    }, primary_tags=[], contextual_tags=["store"], structural_tags=[])


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
        "context_tags": ["Long Island Expressway"],
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
        "context_tags": ["reservation", "glove compartment"],
        "activity_description": "Table conversation about reservation.",
    }, primary_tags=["reservation"], contextual_tags=["glove compartment"], structural_tags=["table"])


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
        "key_moments": ["The woman reads a manuscript", "They mention Pendant Publishing."],
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
        "context_tags": ["Civil War", "Big Bang"],
        "activity_description": "Conversation about Civil War.",
    })

    # The caption remains a qualified independent tag, not transcript speech.
    source = result["claim_provenance"]["tag_sources"]["Big Bang"]
    assert source["sources"] == ["image_caption"]
    assert source["establishes_visible_presence"] is False


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

    assert result["narrative_summary"] == 'Transcript: "I\'m in a transition phase right now."'
    assert "desk" not in result["narrative_summary"].lower()
    assert result["context_tags"] == []


def test_normalize_scene_context_payload_does_not_adjudicate_recognition_by_vocabulary() -> None:
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

    # Recognition quality comes from recognition evidence, not a vocabulary veto.
    assert result["narrative_summary"] != "Minimal visual or dialogue content."
    assert "off oppression wild" not in result["context_tags"]
    assert "oppression wild oppression" not in result["context_tags"]
    for tag in result["context_tags"]:
        assert analyzer._is_transcript_grounded_topic_candidate(tag, "Go off oppression. Wild oppression. Don't.")
        assert result["claim_provenance"]["tag_sources"][tag]["scope"] == "spoken_mention"


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


def test_normalize_scene_context_payload_keeps_visible_objects_contextual_without_a_vocabulary_veto() -> None:
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
        "context_tags": ["potted plant", "wine glass"],
        "activity_description": "Table conversation.",
    }, primary_tags=[], contextual_tags=["potted plant", "wine glass"], structural_tags=[])

    for tag in result["context_tags"]:
        assert result["claim_provenance"]["tag_sources"][tag]["scope"] == "qualified_visual_observation"
        assert result["claim_provenance"]["tag_sources"][tag]["establishes_visible_presence"] is False


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


def test_normalize_scene_context_payload_preserves_grounded_summary_when_no_topic_hint() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A speaker asks to stop, wishes they had insurance, and says the thing never shuts up.",
            "key_moments": [
                "Speaker wishes they had insurance",
                "Speaker says the thing never shuts up",
            ],
            "emotional_arc": "frustration",
            "context_tags": ["insurance", "living room"],
            "activity_description": "Two people converse indoors while expressing annoyance.",
        },
        {
            "caption": "two people standing in a living room",
            "transcript": (
                "Can we stop now? Well, you have insurance. I wish. Unbelievable. Yeah. "
                "What is with this thing? It never shuts up!"
            ),
            "objects": [{"label": "person"}],
        },
    )

    assert "never shuts up" in result["narrative_summary"].lower()
    assert result["narrative_summary"] != "Living room conversation."
    assert any("never shuts up" in km.lower() for km in result["key_moments"])


def test_extract_transcript_topic_hints_avoids_cross_clause_and_non_head_suffix_fragments() -> None:
    hints = analyzer._extract_transcript_topic_hints(  # type: ignore[attr-defined]
        "Yeah, he has a huge problem. No, it was the greatest moment of my life. "
        "I am a marine biologist."
    )
    lowered = {h.lower() for h in hints}
    assert "marine biologist" in lowered
    assert "yeah he" not in lowered
    assert "problem no" not in lowered
    assert "greatest moment" not in lowered
    assert "moment of" not in lowered


def test_normalize_scene_context_payload_preserves_rockaway_ocean_key_moment() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": (
                "Two men converse in a restaurant as one describes hitting golf balls into the ocean at Rockaway."
            ),
            "key_moments": [
                "Speaker describes a scenario involving Rockaway and the ocean",
                "Speaker exclaims about a hole in one",
            ],
            "emotional_arc": "enthusiastic",
            "context_tags": ["restaurant", "ocean", "rockaway"],
            "activity_description": "Two men converse at a restaurant booth.",
        },
        {
            "caption": "two men sitting in a booth at a restaurant",
            "transcript": (
                "So I'm driving out to Rockaway, and I got these clubs in the back of my car, "
                "and I decide I'm gonna hit a few balls into the ocean. What is that, a Titleist? "
                "A hole in one, huh?"
            ),
            "objects": [{"label": "person"}],
        },
    )

    assert "rockaway" in result["narrative_summary"].lower()
    assert "ocean" in result["narrative_summary"].lower()
    assert "hitting a bar with a car" not in result["narrative_summary"].lower()


def test_normalize_scene_context_payload_routes_scene36_detector_only_sandwich_claim_to_attributed_fallback() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Two people talk indoors while one person recounts a story about the sea.",
            "key_moments": [
                "One speaker asks what happened",
                "Individuals talk indoors near a table with a sandwich",
            ],
            "emotional_arc": "curious conversation",
            "context_tags": ["table", "sandwich", "indoor conversation"],
            "activity_description": "Individuals talk indoors near a table with a sandwich.",
        },
        {
            "caption": "a woman sitting at a table talking to a man",
            "transcript": (
                "What happened? Come on. Well, you know that I went out with Elaine "
                "and she told me the whole story about the sea."
            ),
            "objects": [
                {"label": "person", "score": 0.90524},
                {"label": "person", "score": 0.858898},
                {"label": "sandwich", "score": 0.377349},
            ],
        },
    )

    assert result is not None
    assert result["narrative_summary"] == "Two people talk indoors while one person recounts a story about the sea."
    assert result["activity_description"] == "Table conversation."
    assert all("sandwich" not in km.lower() for km in result["key_moments"])
    assert "sandwich" not in [t.lower() for t in result["primary_tags"]]
    assert "sandwich" not in [t.lower() for t in result["contextual_tags"]]
    assert "sandwich" not in [t.lower() for t in result["context_tags"]]
    assert "sandwich" in [t.lower() for t in result["structural_tags"]]
    assert result["claim_provenance"]["tag_sources"]["sandwich"] == {
        "sources": ["object_detect"],
        "scope": "candidate_detection",
        "establishes_visible_presence": False,
    }


def test_normalize_scene_context_payload_rejects_scene9_uncorroborated_caption_and_llm_hallucination() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "Two people converse indoors about hitting a bar with a car.",
            "key_moments": [
                "A man brushes his teeth while talking",
                "They talk about hitting a bar with a car",
            ],
            "emotional_arc": "casual conversation",
            "context_tags": ["indoor conversation"],
            "activity_description": "A man brushes his teeth in a room.",
        },
        {
            "caption": "a man in a blue shirt is brushing his teeth",
            "transcript": "She was at the bar. We were talking for a minute and then we left.",
            "objects": [{"label": "person", "score": 0.923363}],
        },
    )

    assert result is not None
    assert "brushing" not in result["narrative_summary"].lower()
    assert "teeth" not in result["narrative_summary"].lower()
    assert "hitting a bar" not in result["narrative_summary"].lower()
    assert "brushing" not in result["activity_description"].lower()
    assert result["claim_provenance"]["narrative_summary"]["establishes_visible_presence"] is False


def test_normalize_scene_context_payload_preserves_visual_only_positive_evidence_with_caption_provenance() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "A person walks into the water at the beach.",
            "key_moments": ["A person walks into the water at the beach"],
            "emotional_arc": "calm coastal scene",
            "context_tags": ["beach", "water"],
            "activity_description": "Walking into the water at the beach.",
        },
        {
            "caption": "a person is walking into the water at the beach",
            "transcript": "",
            "objects": [{"label": "person", "score": 0.80876}],
        },
    )

    assert result is not None
    assert result["narrative_summary"] == "A person walks into the water at the beach."
    assert result["activity_description"] == "Walking into the water at the beach."
    assert result["key_moments"] == ["A person walks into the water at the beach"]
    assert result["contextual_tags"] == ["beach", "water"]
    assert result["context_tags"] == ["beach", "water"]
    assert result["claim_provenance"]["narrative_summary"] == {
        "source": "scene_context_llm",
        "depends_on": ["image_caption"],
        "qualification": "qualified_visual_observation",
        "establishes_visible_presence": False,
    }
    assert result["claim_provenance"]["tag_sources"]["water"] == {
        "sources": ["image_caption"],
        "scope": "qualified_visual_observation",
        "establishes_visible_presence": False,
    }


def test_normalize_scene_context_payload_attributes_spoken_object_mention_without_visible_presence() -> None:
    result = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": (
                "Two men converse in a restaurant as one mentions ordering a sandwich "
                "and hitting a ball into the ocean at Rockaway."
            ),
            "key_moments": ["Speaker mentions ordering a sandwich and driving to Rockaway"],
            "emotional_arc": "enthusiastic",
            "context_tags": ["restaurant", "ocean", "rockaway", "sandwich"],
            "activity_description": "Restaurant conversation.",
        },
        {
            "caption": "two men sitting in a booth at a restaurant",
            "transcript": (
                "I ordered a sandwich at the counter, drove out to Rockaway, "
                "and hit a ball into the ocean."
            ),
            "objects": [{"label": "person", "score": 0.91}],
        },
    )

    assert result is not None
    assert "sandwich" in result["context_tags"]
    assert result["claim_provenance"]["tag_sources"]["sandwich"] == {
        "sources": ["transcribe"],
        "scope": "spoken_mention",
        "establishes_visible_presence": False,
    }
    assert result["claim_provenance"]["tag_sources"]["restaurant"] == {
        "sources": ["image_caption"],
        "scope": "qualified_visual_observation",
        "establishes_visible_presence": False,
    }


def test_select_scene_object_labels_deduplicates_duplicate_heavy_and_preserves_later_distinct_labels() -> None:
    duplicate_heavy_objects = [
        {"label": "book", "score": round(0.20 + idx * 0.01, 4)} for idx in range(12)
    ] + [
        {"label": "chair", "score": 0.54},
        {"label": "coffee table", "score": 0.42},
        {"label": "curtain", "score": 0.49},
        {"label": "lamp", "score": 0.51},
    ]
    scene_meta = {
        "index": 27,
        "start": 100.0,
        "end": 108.0,
        "caption": "an indoor room with a chair and a curtain",
        "transcript": "",
        "objects": duplicate_heavy_objects,
    }

    _sys_prompt, user_prompt = analyzer._build_scene_context_prompts(scene_meta)  # type: ignore[attr-defined]
    visible_line = next(line for line in user_prompt.splitlines() if line.startswith("- Visible objects:"))
    assert visible_line == "- Visible objects: book, chair, coffee table, curtain, lamp"

    normalized = analyzer._normalize_scene_context_payload(  # type: ignore[attr-defined]
        {
            "narrative_summary": "An indoor room with a chair and a curtain.",
            "activity_description": "Indoor room with a chair and a curtain.",
            "key_moments": ["An indoor room with a chair and a curtain"],
            "emotional_arc": "calm indoor setting",
            "context_tags": ["room", "chair", "curtain", "lamp"],
        },
        scene_meta,
    )
    assert normalized is not None
    assert "curtain" in normalized["context_tags"]
    assert "chair" in normalized["context_tags"]
    assert "lamp" in normalized["structural_tags"]
    assert "object_detect" in normalized["claim_provenance"]["tag_sources"]["curtain"]["sources"]
    assert normalized["claim_provenance"]["tag_sources"]["lamp"] == {
        "sources": ["object_detect"],
        "scope": "candidate_detection",
        "establishes_visible_presence": False,
    }

    fallback = analyzer._scene_context_failure_fallback_payload(  # type: ignore[attr-defined]
        {
            "caption": "a person standing indoors",
            "transcript": "We should talk about the schedule tomorrow morning.",
            "objects": [{"label": "book"} for _ in range(12)] + [{"label": "couch"}],
        }
    )
    assert "couch" in fallback["context_tags"] or "room" in fallback["narrative_summary"].casefold()


def test_select_scene_object_labels_caps_more_than_ten_distinct_labels_in_first_seen_order() -> None:
    many_objects = [
        {"label": "book"},
        {"label": "BOOK"},
        {"label": "chair"},
        {"label": "coffee table"},
        {"label": "Chair"},
        {"label": "curtain"},
        {"label": "lamp"},
        {"label": "lampshade"},
        {"label": "mobile phone"},
        {"label": "person"},
        {"label": "Person"},
        {"label": "backpack"},
        {"label": "bed"},
        {"label": "headboard"},
        {"label": "painting"},
        {"label": "vase"},
    ]
    selected = analyzer._select_scene_object_labels(many_objects, limit=10)  # type: ignore[attr-defined]
    assert selected == [
        "book",
        "chair",
        "coffee table",
        "curtain",
        "lamp",
        "lampshade",
        "mobile phone",
        "person",
        "backpack",
        "bed",
    ]
    assert len(selected) == 10


def test_select_scene_object_labels_handles_mixed_empty_and_invalid_controls() -> None:
    mixed_objects = [
        {"label": "person"},
        {"label": "book"},
        {"label": "laptop"},
        {"label": "laptop"},
        {"label": "person"},
        {"label": "suitcase"},
        {"label": "chair"},
        {"label": "chair"},
    ]
    assert analyzer._select_scene_object_labels(mixed_objects, limit=10) == [  # type: ignore[attr-defined]
        "person",
        "book",
        "laptop",
        "suitcase",
        "chair",
    ]

    for empty_control in ([], None, "not-a-list", 123, {}):
        assert analyzer._select_scene_object_labels(empty_control, limit=10) == []  # type: ignore[attr-defined]

    _sys_empty, user_empty = analyzer._build_scene_context_prompts({"objects": []})  # type: ignore[attr-defined]
    assert "- Visible objects: none" in user_empty

    invalid_controls = [
        None,
        {},
        {"label": None},
        {"label": ""},
        {"label": "   "},
        {"label": 123},
        {"label": True},
        {"label": ["nested"]},
        456,
        True,
        "   ",
        {"name": "  curtain  "},
        {"class": "lamp"},
        "Chair",
        {"label": "CURTAIN"},
    ]
    assert analyzer._select_scene_object_labels(invalid_controls, limit=10) == [  # type: ignore[attr-defined]
        "curtain",
        "lamp",
        "Chair",
    ]


def test_derive_setting_hint_ignores_hedged_caption_places_and_preserves_unhedged() -> None:
    hedged_hint = analyzer._derive_setting_hint(  # type: ignore[attr-defined]
        (
            "Two people stand indoors in front of wood paneling. "
            "The setting appears to be a cozy indoor environment, possibly a home office or living room."
        ),
        [],
    )
    assert hedged_hint is None

    unhedged_hint = analyzer._derive_setting_hint(  # type: ignore[attr-defined]
        "A man is sitting indoors in a bathroom setting.",
        [],
    )
    assert unhedged_hint == "bathroom"
