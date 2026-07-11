import pytest

from tests.conftest import pytest_collection_modifyitems
from tests.runtime_profile import (
    expected_epoch_collections,
    require_live_profile,
    require_runtime_evidence,
    selected_runtime_epoch,
)


class _FakeConfig:
    def __init__(self, profile):
        self.profile = profile

    def getoption(self, _name):
        return self.profile


class _FakeItem:
    def __init__(self, *keywords):
        self.keywords = set(keywords)
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)


def test_isolated_profile_skips_live_runtime_checks():
    with pytest.raises(pytest.skip.Exception):
        require_live_profile("isolated", "Qdrant witness")


def test_isolated_collection_gate_skips_all_live_runtime_items():
    live_item = _FakeItem("live_runtime")
    hermetic_item = _FakeItem()
    pytest_collection_modifyitems(_FakeConfig("isolated"), [live_item, hermetic_item])

    assert [marker.mark.name for marker in live_item.markers] == ["skip"]
    assert hermetic_item.markers == []


def test_live_collection_gate_does_not_skip_runtime_items():
    live_item = _FakeItem("live_runtime")
    pytest_collection_modifyitems(_FakeConfig("live"), [live_item])
    assert live_item.markers == []


@pytest.mark.parametrize("profile", ["live", "golden"])
def test_live_profiles_fail_when_required_evidence_is_missing(profile):
    with pytest.raises(pytest.fail.Exception, match="required runtime evidence unavailable"):
        require_runtime_evidence(profile, False, "Qdrant is not listening")


@pytest.mark.parametrize("profile", ["live", "golden"])
def test_live_profiles_accept_present_runtime_evidence(profile):
    require_live_profile(profile, "Qdrant witness")
    require_runtime_evidence(profile, True, "unused")


def test_golden_profile_rejects_an_unpinned_epoch():
    with pytest.raises(pytest.fail.Exception, match="golden epoch mismatch"):
        selected_runtime_epoch("golden", "epoch_not_the_golden_authority")


def test_live_profile_derives_exact_collection_names():
    epoch_id = "epoch_test_runtime"
    assert expected_epoch_collections("live", epoch_id) == {
        "audio": "goodq_audio_epoch_test_runtime",
        "clip": "goodq_clip_epoch_test_runtime",
        "dino": "goodq_dino_epoch_test_runtime",
        "text": "goodq_text_epoch_test_runtime",
    }
