from __future__ import annotations
from typing import Any, Dict, List

import os


def face_embed(item: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    path = item.get("source_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return {"faces": [], "faces_meta": {"status": "no_file"}}
    try:
        import face_recognition  # type: ignore
        import numpy as np  # type: ignore

        img = face_recognition.load_image_file(path)
        locs = face_recognition.face_locations(img)
        encs = face_recognition.face_encodings(img, locs)
        faces: List[Dict[str, Any]] = []
        for (top, right, bottom, left), enc in zip(locs, encs):
            faces.append({
                "bbox": [int(left), int(top), int(right), int(bottom)],
                "encoding": [float(x) for x in (enc.tolist() if hasattr(enc, "tolist") else list(enc))],
            })
        return {"faces": faces, "faces_meta": {"status": "ok", "engine": "face_recognition"}}
    except Exception:
        # Fallback to facenet-pytorch (no dlib dependency)
        try:
            import torch  # type: ignore
            import numpy as np  # type: ignore
            from PIL import Image  # type: ignore
            from torchvision import transforms  # type: ignore
            from facenet_pytorch import MTCNN, InceptionResnetV1  # type: ignore

            device = "cuda" if getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
            mtcnn = MTCNN(keep_all=True, device=device)
            resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)

            img = Image.open(path).convert("RGB")
            boxes, _ = mtcnn.detect(img)
            faces: List[Dict[str, Any]] = []
            if boxes is not None:
                for b in boxes:
                    x1, y1, x2, y2 = [int(v) for v in b]
                    crop = img.crop((x1, y1, x2, y2)).resize((160, 160))
                    t = transforms.ToTensor()(crop).unsqueeze(0).to(device)
                    with torch.no_grad():
                        emb = resnet(t).cpu().numpy()[0].astype(float).tolist()
                    faces.append({"bbox": [x1, y1, x2, y2], "encoding": emb})
            return {"faces": faces, "faces_meta": {"status": "ok", "engine": "facenet-pytorch"}}
        except Exception as e2:
            return {"faces": [], "faces_meta": {"status": "error", "error": str(e2)}}
