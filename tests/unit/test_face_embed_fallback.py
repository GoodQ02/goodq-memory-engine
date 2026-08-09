from __future__ import annotations

from pathlib import Path

from steps.face_embed import step as face_step


def test_face_embed_uses_yunet_sface_as_primary(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fixture")

    monkeypatch.setattr(
        face_step,
        "_opencv_yunet_sface_embed",
        lambda _path: [{"bbox": [1, 2, 3, 4], "encoding": [0.1, 0.2], "engine": face_step.PRIMARY_ENGINE, "embedding_dimension": 2}],
    )

    result = face_step.face_embed({"source_path": str(image_path)}, {})

    assert result["faces_meta"] == {
        "status": "ok",
        "engine": "opencv-yunet-sface",
        "fallback_used": False,
        "embedding_dimension": 2,
    }
    assert result["faces"][0]["engine"] == "opencv-yunet-sface"
    assert result["faces"][0]["embedding_dimension"] == 2


def test_face_embed_uses_dlib_only_as_explicit_degraded_fallback(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fixture")

    monkeypatch.setattr(
        face_step,
        "_opencv_yunet_sface_embed",
        lambda _path: (_ for _ in ()).throw(face_step.PrimaryFaceEngineUnavailable("missing sealed SFace model")),
    )
    monkeypatch.setattr(
        face_step,
        "_face_recognition_embed",
        lambda _path: [{"bbox": [1, 2, 3, 4], "encoding": [0.1, 0.2, 0.3], "engine": face_step.FALLBACK_ENGINE, "embedding_dimension": 3}],
    )

    result = face_step.face_embed({"source_path": str(image_path)}, {})

    assert result["faces_meta"] == {
        "status": "degraded",
        "engine": "face_recognition",
        "primary_engine": "opencv-yunet-sface",
        "fallback_used": True,
        "fallback_reason": "missing sealed SFace model",
        "embedding_dimension": 3,
    }
    assert result["faces"][0]["engine"] == "face_recognition"
    assert result["faces"][0]["embedding_dimension"] == 3


def test_face_embed_surfaces_error_when_primary_and_fallback_are_unavailable(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fixture")

    monkeypatch.setattr(
        face_step,
        "_opencv_yunet_sface_embed",
        lambda _path: (_ for _ in ()).throw(face_step.PrimaryFaceEngineUnavailable("YuNet model digest mismatch")),
    )
    monkeypatch.setattr(
        face_step,
        "_face_recognition_embed",
        lambda _path: (_ for _ in ()).throw(RuntimeError("dlib unavailable")),
    )

    result = face_step.face_embed({"source_path": str(image_path)}, {})

    assert result["faces"] == []
    assert result["faces_meta"]["status"] == "error"
    assert result["faces_meta"]["primary_engine"] == "opencv-yunet-sface"
    assert result["faces_meta"]["fallback_engine"] == "face_recognition"
    assert "YuNet model digest mismatch" in result["faces_meta"]["primary_error"]
    assert "dlib unavailable" in result["faces_meta"]["fallback_error"]


def test_face_embed_rejects_missing_source_file():
    result = face_step.face_embed({"source_path": "not-a-real-file.jpg"}, {})

    assert result == {"faces": [], "faces_meta": {"status": "no_file"}}
