"""
Phase 4 Audio Processor - Test Script

Tests the Phase 4 heavy audio processing on segmented chunks.
"""

import sys
import json
import yaml
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from steps.audio.segmentation.phase4_audio_processor import process_segmented_audio


def test_phase4():
    """Test Phase 4 audio processing"""
    
    print("=" * 80)
    print("PHASE 4 AUDIO PROCESSOR TEST")
    print("=" * 80)
    
    # Test paths
    test_manifest = "L:/_DATA/GoodQ_Data/processing/test_video/metadata/segmentation.json"
    test_video = "L:/_DATA/GoodQ_Data/inbox/test_video.mp4"
    test_output = "L:/_DATA/GoodQ_Data/processing/test_video"
    config_path = "L:/goodq4all/configs/goodq_config.yaml"
    
    # Check if test manifest exists
    if not Path(test_manifest).exists():
        print(f"\n[FAIL] Test manifest not found: {test_manifest}")
        print("\nPlease run Phase 3 first to generate segmentation manifest.")
        print("Example: python -m steps.audio.segmentation.phase3_chunk_builder")
        return False
    
    # Load config
    print(f"\n[LOG] Loading config: {config_path}")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Load manifest to show stats
    print(f"\n[LOG] Loading segmentation manifest: {test_manifest}")
    with open(test_manifest, 'r') as f:
        manifest = json.load(f)
    
    segments = manifest.get('segments', [])
    speech_segments = [s for s in segments if s.get('vad_speech', False)]
    
    print(f"\n[STATS] Manifest Stats:")
    print(f"  Total segments: {len(segments)}")
    print(f"  Speech segments: {len(speech_segments)}")
    print(f"  Non-speech segments: {len(segments) - len(speech_segments)}")
    print(f"  Total duration: {manifest.get('total_duration', 0):.1f}s")
    
    # Run Phase 4
    print("\n" + "=" * 80)
    print("RUNNING PHASE 4 PROCESSING")
    print("=" * 80)
    
    try:
        result = process_segmented_audio(
            test_manifest,
            test_video,
            test_output,
            config
        )
        
        print("\n" + "=" * 80)
        print("[OK] PHASE 4 COMPLETE!")
        print("=" * 80)
        
        # Show results
        processed_segments = result.get('segments', [])
        transcribed = [s for s in processed_segments if s.get('transcript')]
        diarized = [s for s in processed_segments if s.get('diarization')]
        errors = [s for s in processed_segments if s.get('wsl2_error')]
        
        print(f"\n[STATS] Processing Results:")
        print(f"  Total segments processed: {len(processed_segments)}")
        print(f"  Successfully transcribed: {len(transcribed)}")
        print(f"  Successfully diarized: {len(diarized)}")
        print(f"  Errors: {len(errors)}")
        
        if transcribed:
            print(f"\n[NOTE] Sample Transcription (first speech segment):")
            first = transcribed[0]
            print(f"  Segment ID: {first['id']}")
            print(f"  Time: {first['start']:.2f}s - {first['end']:.2f}s")
            print(f"  Language: {first.get('language', 'unknown')}")
            print(f"  Speakers: {first.get('speaker_count', 0)}")
            print(f"  Text: {first.get('transcript', '')[:200]}...")
        
        # Show output location
        output_manifest = Path(test_output) / "metadata" / "segmentation_enhanced.json"
        print(f"\n[SAVE] Enhanced manifest saved to:")
        print(f"  {output_manifest}")
        
        return True
    
    except Exception as e:
        print(f"\n[FAIL] Phase 4 failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_phase4()
    sys.exit(0 if success else 1)
