from api.utils.identity_evidence_pack import build_identity_evidence_pack


def test_identity_role_is_visible_but_not_converted_to_pairwise_claim() -> None:
    pack = build_identity_evidence_pack(
        [
            {"id": "joe", "display_name": "Joe", "role": "subject"},
            {"id": "maria", "display_name": "Maria", "role": "Cousin"},
        ],
        ["Joe", "Maria"],
    )
    assert pack["claim_status"] == "not_established"
    assert pack["relationships"] == []
    assert {label["value"] for label in pack["identity_labels"]} == {"subject", "Cousin"}


def test_explicit_curated_relationship_is_the_only_established_claim() -> None:
    pack = build_identity_evidence_pack(
        [
            {"id": "joe", "display_name": "Joe", "role": "subject"},
            {
                "id": "maria",
                "display_name": "Maria",
                "role": "Cousin",
                "relationships": [{"target_id": "joe", "type": "cousin"}],
            },
        ],
        ["Joe", "Maria"],
    )
    assert pack["claim_status"] == "established"
    assert pack["relationships"] == [{
        "source_id": "maria",
        "target_id": "joe",
        "type": "cousin",
        "authority": "curated_roster_relationship",
    }]


def test_unrelated_cooccurrence_is_not_a_relationship_input() -> None:
    pack = build_identity_evidence_pack(
        [{"id": "maria", "display_name": "Maria", "role": "Cousin"}],
        ["Maria", "Unknown"],
    )
    assert pack["claim_status"] == "not_established"
    assert len(pack["identities"]) == 1
