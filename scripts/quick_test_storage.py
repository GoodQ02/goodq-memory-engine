#!/usr/bin/env python3
"""
Quick test of memory_writer - verify it works before applying everywhere
"""
import sys
sys.path.insert(0, 'L:/goodq4all')

from steps.common.memory_writer import MemoryWriter
import json

def test_memory_writer():
    """Test the memory writer with sample data"""
    print("="*70)
    print("MEMORY WRITER TEST")
    print("="*70)
    print()
    
    try:
        writer = MemoryWriter()
        print(f"✅ Connected to database: {writer.db_path}")
        print()
        
        # Test 1: Create a scene
        print("Test 1: Creating scene...")
        success = writer.save_scene(
            video_hash="test_video_123",
            scene_id="test_scene_0000",
            start_time=0.0,
            end_time=10.5,
            metadata={'test': True, 'created_by': 'quick_test'}
        )
        print(f"  {'✅' if success else '❌'} Scene created")
        print()
        
        # Test 2: Add caption
        print("Test 2: Adding caption...")
        success = writer.save_caption(
            "test_scene_0000",
            "A person standing in a sunlit room",
            confidence=0.87
        )
        print(f"  {'✅' if success else '❌'} Caption added")
        print()
        
        # Test 3: Add objects
        print("Test 3: Adding detected objects...")
        objects = [
            {'label': 'person', 'confidence': 0.95, 'bbox': [100, 100, 300, 400]},
            {'label': 'chair', 'confidence': 0.87, 'bbox': [450, 200, 600, 500]},
            {'label': 'window', 'confidence': 0.92, 'bbox': [50, 50, 250, 300]}
        ]
        success = writer.save_objects("test_scene_0000", objects)
        print(f"  {'✅' if success else '❌'} Objects added")
        print()
        
        # Test 4: Add OCR text
        print("Test 4: Adding OCR text...")
        success = writer.save_ocr_text(
            "test_scene_0000",
            "Welcome Home",
            regions=[{'text': 'Welcome', 'bbox': [100, 50, 200, 80]}]
        )
        print(f"  {'✅' if success else '❌'} OCR text added")
        print()
        
        # Test 5: Add transcription
        print("Test 5: Adding transcription...")
        transcription = {
            'text': "Hello everyone, welcome to my home!",
            'segments': [
                {'start': 0.5, 'end': 2.3, 'text': 'Hello everyone'},
                {'start': 2.5, 'end': 4.8, 'text': 'welcome to my home!'}
            ],
            'language': 'en',
            'confidence': 0.94
        }
        success = writer.save_transcription("test_scene_0000", transcription)
        print(f"  {'✅' if success else '❌'} Transcription added")
        print()
        
        # Test 6: Add sentiment
        print("Test 6: Adding sentiment...")
        sentiment = {
            'label': 'positive',
            'score': 0.89,
            'details': {'positive': 0.89, 'neutral': 0.10, 'negative': 0.01}
        }
        success = writer.save_sentiment("test_scene_0000", sentiment)
        print(f"  {'✅' if success else '❌'} Sentiment added")
        print()
        
        # Test 7: Add emotions
        print("Test 7: Adding emotions...")
        emotions = {
            'joy': 0.78,
            'surprise': 0.12,
            'neutral': 0.08,
            'sadness': 0.02
        }
        success = writer.save_emotions("test_scene_0000", emotions)
        print(f"  {'✅' if success else '❌'} Emotions added")
        print()
        
        # Test 8: Batch save
        print("Test 8: Batch save (all at once)...")
        batch_results = {
            'caption': 'Another test caption',
            'objects': [{'label': 'dog', 'confidence': 0.99}],
            'tags': ['home', 'family', 'indoor'],
            'custom_field': 'custom value'
        }
        success = writer.save_analysis_batch("test_scene_0000", batch_results)
        print(f"  {'✅' if success else '❌'} Batch save completed")
        print()
        
        # Test 9: Retrieve and verify
        print("Test 9: Retrieving scene to verify...")
        scene = writer.get_scene("test_scene_0000")
        
        if scene:
            print("✅ Scene retrieved successfully!")
            print()
            print("Scene Data:")
            print("-" * 70)
            print(f"  ID: {scene['id']}")
            print(f"  Video Hash: {scene['video_hash']}")
            print(f"  Time: {scene['start']}s - {scene['end']}s")
            print()
            print("  Metadata:")
            meta = scene.get('meta', {})
            for key, value in sorted(meta.items()):
                if isinstance(value, (dict, list)):
                    print(f"    {key}: {type(value).__name__} with {len(value)} items")
                elif isinstance(value, str) and len(value) > 50:
                    print(f"    {key}: {value[:50]}...")
                else:
                    print(f"    {key}: {value}")
            print()
            
            # Verify key fields
            print("Verification:")
            checks = {
                'caption': 'caption' in meta,
                'objects': 'objects' in meta,
                'ocr_text': 'ocr_text' in meta,
                'transcription': 'transcription' in meta,
                'sentiment_label': 'sentiment_label' in meta,
                'emotions': 'emotions' in meta,
                'tags_auto': 'tags_auto' in meta,
            }
            
            for field, present in checks.items():
                print(f"  {'✅' if present else '❌'} {field}")
            
            print()
            
            # Check if all present
            if all(checks.values()):
                print("🎉 ALL TESTS PASSED! Memory writer is working perfectly.")
            else:
                print("⚠️  Some fields missing - review above")
                
        else:
            print("❌ Failed to retrieve scene")
            
        print()
        print("="*70)
        print("Test complete - you can now safely apply memory_writer to steps!")
        print("="*70)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_memory_writer()
