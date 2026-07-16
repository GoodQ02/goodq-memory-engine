from scripts.ucf import ucf_ledger


def test_ingestion_and_scene_detection_load_canonical_ucf_ledger():
    from cli.run_ingestion import _load_ucf_ledger as load_ingestion_ledger
    from steps.video_scene_detect.step import _load_ucf_ledger as load_scene_ledger

    assert load_ingestion_ledger() is ucf_ledger
    assert load_scene_ledger() is ucf_ledger
