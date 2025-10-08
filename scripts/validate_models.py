"""
Comprehensive model validation script to ensure all steps produce actual output.
Tests each key model with sample data to verify it's working properly.
"""
import os
import sys
import json
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.steps.common.config_loader import load_configs


def test_object_detection():
    """Test YOLO object detection"""
    print("\n=== Testing Object Detection (YOLO) ===")
    from steps.steps.object_detect.step import object_detect
    
    test_img = "L:\\GoodQ_4_All\\logs\\ingest_full\\1987_1988\\frames\\scene_0000.jpg"
    if not os.path.isfile(test_img):
        print(f"❌ Test image not found: {test_img}")
        return False
    
    cfg = load_configs({})
    item = {"source_path": test_img, "modality": "image"}
    result = object_detect(item, cfg)
    
    objects = result.get("objects", [])
    print(f"Detected {len(objects)} objects")
    if objects:
        print(f"Sample object: {objects[0]}")
        print("✅ Object detection WORKING")
        return True
    else:
        meta = result.get("detect_meta", {})
        print(f"❌ No objects detected. Meta: {meta}")
        return False


def test_image_caption():
    """Test BLIP image captioning"""
    print("\n=== Testing Image Captioning (BLIP) ===")
    from steps.steps.image_caption.step import image_caption
    
    test_img = "L:\\GoodQ_4_All\\logs\\ingest_full\\1987_1988\\frames\\scene_0000.jpg"
    if not os.path.isfile(test_img):
        print(f"❌ Test image not found: {test_img}")
        return False
    
    cfg = load_configs({})
    item = {"source_path": test_img, "modality": "image"}
    result = image_caption(item, cfg)
    
    caption = result.get("caption")
    print(f"Caption: {caption}")
    if caption and isinstance(caption, str) and len(caption) > 0:
        print("✅ Image captioning WORKING")
        return True
    else:
        meta = result.get("caption_meta", {})
        print(f"❌ No caption generated. Meta: {meta}")
        return False


def test_ocr():
    """Test OCR (EasyOCR/Tesseract)"""
    print("\n=== Testing OCR ===")
    from steps.steps.image_ocr.step import image_ocr
    
    test_img = "L:\\GoodQ_4_All\\logs\\ingest_full\\1987_1988\\frames\\scene_0000.jpg"
    if not os.path.isfile(test_img):
        print(f"❌ Test image not found: {test_img}")
        return False
    
    cfg = load_configs({})
    item = {"source_path": test_img, "modality": "image"}
    result = image_ocr(item, cfg)
    
    ocr_text = result.get("ocr_text")
    print(f"OCR Text: {ocr_text or '(none)'}")
    meta = result.get("ocr_meta", {})
    print(f"OCR Meta: {meta}")
    if ocr_text:
        print("✅ OCR found text")
        return True
    else:
        print("⚠️  No text found (might be normal for this image)")
        return None  # Not necessarily a failure


def test_audio_transcription():
    """Test Whisper transcription"""
    print("\n=== Testing Audio Transcription (Whisper) ===")
    from steps.steps.audio_transcribe.step import audio_transcribe
    
    test_audio = "L:\\GoodQ_4_All\\logs\\ingest_full\\1987_1988\\audio\\scene_0000.wav"
    if not os.path.isfile(test_audio):
        print(f"❌ Test audio not found: {test_audio}")
        return False
    
    cfg = load_configs({})
    item = {"source_path": test_audio, "modality": "audio"}
    result = audio_transcribe(item, cfg)
    
    transcript = result.get("transcript")
    meta = result.get("transcript_meta", {})
    print(f"Transcript: {transcript or '(none)'}")
    print(f"Status: {meta.get('status')}")
    print(f"Engine: {meta.get('engine')}")
    print(f"Chunks processed: {len(meta.get('chunks', []))}")
    
    if transcript and len(transcript) > 0:
        print("✅ Transcription WORKING")
        return True
    else:
        print("❌ No transcript generated")
        if meta.get('chunks'):
            print("Chunk details:")
            for i, chunk in enumerate(meta['chunks'][:3]):
                print(f"  Chunk {i}: status={chunk.get('status')}, text={chunk.get('text')}")
        return False


def test_sentiment():
    """Test sentiment analysis"""
    print("\n=== Testing Sentiment Analysis ===")
    from steps.steps.sentiment.step import sentiment
    
    cfg = load_configs({})
    item = {"transcript": "This is amazing! I love this project. It works great.", "modality": "text"}
    result = sentiment(item, cfg)
    
    sent = result.get("sentiment")
    meta = result.get("sentiment_meta", {})
    print(f"Sentiment: {sent}")
    print(f"Meta: {meta}")
    if sent and sent.get("label"):
        print("✅ Sentiment analysis WORKING")
        return True
    else:
        print("❌ No sentiment generated")
        return False


def test_emotion_classify():
    """Test emotion classification"""
    print("\n=== Testing Emotion Classification ===")
    from steps.steps.emotion_classify.step import emotion_classify
    
    cfg = load_configs({})
    item = {"transcript": "I'm so excited and happy about this! This is wonderful news!", "modality": "text"}
    result = emotion_classify(item, cfg)
    
    emotions = result.get("emotions")
    meta = result.get("emotion_meta", {})
    print(f"Emotions: {emotions}")
    print(f"Meta: {meta}")
    if emotions and len(emotions) > 0:
        print("✅ Emotion classification WORKING")
        return True
    else:
        print("❌ No emotions generated")
        return False


def test_tagger():
    """Test NER tagging"""
    print("\n=== Testing Tagger (NER) ===")
    from steps.steps.tagger.step import tagger
    
    cfg = load_configs({})
    item = {"transcript": "John Smith went to New York City and visited Microsoft headquarters.", "modality": "text"}
    result = tagger(item, cfg)
    
    tags = result.get("tags", [])
    entities = result.get("entities", [])
    print(f"Tags: {tags}")
    print(f"Entities: {entities}")
    if tags or entities:
        print("✅ Tagger WORKING")
        return True
    else:
        print("❌ No tags/entities generated")
        return False


def test_text_embed():
    """Test text embedding"""
    print("\n=== Testing Text Embedding ===")
    from steps.steps.text_embed.step import text_embed
    
    cfg = load_configs({})
    item = {"transcript": "This is a test sentence for embedding.", "modality": "text"}
    result = text_embed(item, cfg)
    
    meta = result.get("embedding_meta", {})
    print(f"Embedding Meta: {meta}")
    if meta.get("status") == "ok":
        print("✅ Text embedding WORKING")
        return True
    else:
        print(f"❌ Text embedding failed: {meta.get('status')}")
        return False


def main():
    """Run all validation tests"""
    print("="*60)
    print("MODEL VALIDATION TEST SUITE")
    print("="*60)
    
    results = {
        "Object Detection": test_object_detection(),
        "Image Captioning": test_image_caption(),
        "OCR": test_ocr(),
        "Audio Transcription": test_audio_transcription(),
        "Sentiment Analysis": test_sentiment(),
        "Emotion Classification": test_emotion_classify(),
        "NER Tagger": test_tagger(),
        "Text Embedding": test_text_embed(),
    }
    
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    
    for name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print("\n⚠️  Some models are not producing output. Check configuration and model files.")
        return 1
    else:
        print("\n✅ All critical models are working!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
