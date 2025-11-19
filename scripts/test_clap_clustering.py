"""
Phase 1 Validation: Test CLAP-based Speaker Clustering

This script compares CLAP embeddings vs PyAnnote diarization to see if CLAP
can improve speaker clustering in noisy audio environments.

Usage:
    python scripts/test_clap_clustering.py <audio_file.wav>

Requirements:
    - Audio file with multiple speakers (ideally noisy)
    - CLAP model already loaded in your environment
    - PyAnnote pipeline configured

Author: GoodQ4All Team
Date: 2025-11-18
"""

import sys
import os
from pathlib import Path
import numpy as np
import librosa
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
import torch

# Add goodq4all to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from steps.audio_embed_clap.step import _load_clap
from pyannote.audio import Pipeline


def extract_clap_chunks(audio_path: str, window_seconds: float = 2.0, overlap_ratio: float = 0.5):
    """
    Extract CLAP embeddings from audio chunks
    
    Args:
        audio_path: Path to audio file
        window_seconds: Chunk size in seconds
        overlap_ratio: Overlap between chunks (0.0-1.0)
    
    Returns:
        List of dicts with {start, end, embedding}
    """
    print(f"\n{'='*70}")
    print("PHASE 1: CLAP CHUNK EXTRACTION")
    print(f"{'='*70}")
    print(f"Audio: {audio_path}")
    print(f"Window: {window_seconds}s, Overlap: {overlap_ratio*100:.0f}%")
    
    # Load audio
    print("\nLoading audio...")
    y, sr = librosa.load(audio_path, sr=48000)
    duration = len(y) / sr
    print(f"✅ Loaded: {duration:.1f}s @ {sr}Hz")
    
    # Load CLAP model
    print("\nLoading CLAP model...")
    clap_model, clap_proc = _load_clap()
    if clap_model is None:
        raise RuntimeError("Failed to load CLAP model!")
    print("✅ CLAP model loaded")
    
    # Calculate chunk parameters
    window_samples = int(window_seconds * sr)
    hop_samples = int(window_samples * (1 - overlap_ratio))
    
    print(f"\nExtracting CLAP embeddings...")
    print(f"  Window: {window_samples} samples ({window_seconds}s)")
    print(f"  Hop: {hop_samples} samples ({hop_samples/sr:.2f}s)")
    
    embeddings = []
    timestamps = []
    
    for i in range(0, len(y) - window_samples + 1, hop_samples):
        chunk = y[i:i+window_samples]
        start_time = i / sr
        end_time = (i + window_samples) / sr
        
        # Extract CLAP embedding using your existing code
        try:
            batch = clap_proc(audios=[chunk], sampling_rate=sr, return_tensors="pt")
            if 'input_features' not in batch:
                print(f"⚠️  Warning: No input_features for chunk at {start_time:.1f}s")
                continue
            
            features = batch['input_features'].to('cuda' if torch.cuda.is_available() else 'cpu')
            
            with torch.no_grad():
                emb = clap_model.get_audio_features(input_features=features)
            
            emb_np = emb.cpu().numpy().flatten()  # 512-d vector
            
            embeddings.append(emb_np)
            timestamps.append({'start': start_time, 'end': end_time})
            
            if len(embeddings) % 10 == 0:
                print(f"  Extracted {len(embeddings)} chunks... ({end_time:.1f}s)")
        
        except Exception as e:
            print(f"⚠️  Error at {start_time:.1f}s: {e}")
            continue
    
    print(f"\n✅ Extracted {len(embeddings)} CLAP embeddings")
    print(f"   Embedding shape: {embeddings[0].shape if embeddings else 'N/A'}")
    
    return np.array(embeddings), timestamps


def cluster_clap_embeddings(embeddings: np.ndarray, min_speakers: int = 2, max_speakers: int = 10):
    """
    Cluster CLAP embeddings to detect speakers
    
    Args:
        embeddings: Array of CLAP embeddings (N x 512)
        min_speakers: Minimum number of speakers
        max_speakers: Maximum number of speakers to try
    
    Returns:
        Best clustering labels and number of speakers
    """
    print(f"\n{'='*70}")
    print("PHASE 2: CLAP-BASED CLUSTERING")
    print(f"{'='*70}")
    print(f"Embeddings: {embeddings.shape[0]} chunks x {embeddings.shape[1]} dims")
    
    best_score = -1
    best_labels = None
    best_n = min_speakers
    
    print(f"\nTesting {min_speakers}-{max_speakers} speakers...")
    
    for n_speakers in range(min_speakers, max_speakers + 1):
        try:
            clustering = AgglomerativeClustering(
                n_clusters=n_speakers,
                linkage='ward',
            )
            labels = clustering.fit_predict(embeddings)
            
            # Calculate silhouette score (quality metric)
            score = silhouette_score(embeddings, labels)
            
            print(f"  {n_speakers} speakers: silhouette={score:.3f}")
            
            if score > best_score:
                best_score = score
                best_labels = labels
                best_n = n_speakers
        
        except Exception as e:
            print(f"  {n_speakers} speakers: FAILED ({e})")
            continue
    
    print(f"\n✅ Best clustering: {best_n} speakers (silhouette={best_score:.3f})")
    
    # Print speaker distribution
    unique, counts = np.unique(best_labels, return_counts=True)
    print(f"\nSpeaker distribution:")
    for spk, cnt in zip(unique, counts):
        print(f"  Speaker {spk}: {cnt} chunks ({cnt/len(best_labels)*100:.1f}%)")
    
    return best_labels, best_n


def run_pyannote_diarization(audio_path: str):
    """
    Run PyAnnote diarization for comparison
    
    Args:
        audio_path: Path to audio file
    
    Returns:
        Diarization result
    """
    print(f"\n{'='*70}")
    print("PHASE 3: PYANNOTE DIARIZATION (BASELINE)")
    print(f"{'='*70}")
    
    try:
        print("Loading PyAnnote pipeline...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization@2.1",
            use_auth_token=os.environ.get("HF_TOKEN")
        )
        
        # Move to GPU if available
        if torch.cuda.is_available():
            pipeline = pipeline.to(torch.device("cuda"))
            print("✅ Pipeline on GPU")
        else:
            print("⚠️  Pipeline on CPU")
        
        print(f"\nRunning diarization on {audio_path}...")
        diarization = pipeline(audio_path)
        
        # Extract speaker info
        speakers = set()
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speakers.add(speaker)
            segments.append({
                'start': turn.start,
                'end': turn.end,
                'speaker': speaker,
            })
        
        print(f"✅ Diarization complete")
        print(f"   Detected speakers: {len(speakers)}")
        print(f"   Total segments: {len(segments)}")
        
        # Print speaker distribution
        from collections import Counter
        speaker_counts = Counter(seg['speaker'] for seg in segments)
        print(f"\nSpeaker distribution:")
        for spk, cnt in speaker_counts.items():
            total_time = sum(seg['end'] - seg['start'] for seg in segments if seg['speaker'] == spk)
            print(f"  {spk}: {cnt} segments, {total_time:.1f}s total")
        
        return diarization, speakers, segments
    
    except Exception as e:
        print(f"❌ PyAnnote failed: {e}")
        return None, set(), []


def compare_results(clap_labels, timestamps, pyannote_segments):
    """
    Compare CLAP clustering vs PyAnnote diarization
    
    Args:
        clap_labels: CLAP cluster labels per chunk
        timestamps: Timestamps for each chunk
        pyannote_segments: PyAnnote diarization segments
    """
    print(f"\n{'='*70}")
    print("PHASE 4: COMPARISON")
    print(f"{'='*70}")
    
    # Convert CLAP chunks to timeline
    clap_speakers = len(set(clap_labels))
    pyannote_speakers = len(set(seg['speaker'] for seg in pyannote_segments))
    
    print(f"\nSpeaker Count:")
    print(f"  CLAP:     {clap_speakers} speakers")
    print(f"  PyAnnote: {pyannote_speakers} speakers")
    print(f"  Difference: {abs(clap_speakers - pyannote_speakers)} speakers")
    
    # Calculate agreement on overlapping regions
    agreements = []
    
    for i, (label, ts) in enumerate(zip(clap_labels, timestamps)):
        chunk_mid = (ts['start'] + ts['end']) / 2
        
        # Find corresponding PyAnnote speaker at this time
        pyannote_speaker = None
        for seg in pyannote_segments:
            if seg['start'] <= chunk_mid <= seg['end']:
                pyannote_speaker = seg['speaker']
                break
        
        if pyannote_speaker is not None:
            agreements.append(1)  # Both have a speaker here
        else:
            agreements.append(0)  # PyAnnote has no speaker here
    
    coverage = np.mean(agreements) * 100
    print(f"\nTemporal Coverage:")
    print(f"  CLAP chunks with PyAnnote speaker: {coverage:.1f}%")
    
    # Calculate speaker transitions
    clap_transitions = sum(1 for i in range(1, len(clap_labels)) if clap_labels[i] != clap_labels[i-1])
    pyannote_transitions = len(pyannote_segments) - pyannote_speakers
    
    print(f"\nSpeaker Transitions:")
    print(f"  CLAP:     {clap_transitions} transitions")
    print(f"  PyAnnote: {pyannote_transitions} transitions")
    
    return {
        'clap_speakers': clap_speakers,
        'pyannote_speakers': pyannote_speakers,
        'coverage': coverage,
        'clap_transitions': clap_transitions,
        'pyannote_transitions': pyannote_transitions,
    }


def visualize_comparison(clap_labels, timestamps, pyannote_segments, output_path: str = None):
    """
    Create visualization comparing CLAP vs PyAnnote
    
    Args:
        clap_labels: CLAP cluster labels
        timestamps: Timestamps for chunks
        pyannote_segments: PyAnnote segments
        output_path: Optional path to save figure
    """
    print(f"\n{'='*70}")
    print("PHASE 5: VISUALIZATION")
    print(f"{'='*70}")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8))
    
    # Plot CLAP clustering
    for i, (label, ts) in enumerate(zip(clap_labels, timestamps)):
        ax1.barh(0, ts['end'] - ts['start'], left=ts['start'], height=0.8, 
                 color=f"C{label % 10}", edgecolor='white', linewidth=0.5)
    
    ax1.set_ylabel('CLAP Speaker', fontsize=12, fontweight='bold')
    ax1.set_title('CLAP-based Speaker Clustering (Chunk-level)', fontsize=14, fontweight='bold')
    ax1.set_ylim(-0.5, 0.5)
    ax1.set_yticks([])
    ax1.grid(axis='x', alpha=0.3)
    
    # Plot PyAnnote diarization
    speaker_to_id = {spk: i for i, spk in enumerate(sorted(set(seg['speaker'] for seg in pyannote_segments)))}
    
    for seg in pyannote_segments:
        spk_id = speaker_to_id[seg['speaker']]
        ax2.barh(0, seg['end'] - seg['start'], left=seg['start'], height=0.8,
                 color=f"C{spk_id % 10}", edgecolor='white', linewidth=0.5)
    
    ax2.set_ylabel('PyAnnote Speaker', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
    ax2.set_title('PyAnnote Speaker Diarization (Segment-level)', fontsize=14, fontweight='bold')
    ax2.set_ylim(-0.5, 0.5)
    ax2.set_yticks([])
    ax2.grid(axis='x', alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✅ Saved visualization to: {output_path}")
    else:
        print("✅ Displaying visualization...")
        plt.show()


def main():
    """Main validation script"""
    print(f"\n{'='*70}")
    print("🔬 PHASE 1: CLAP PRE-EMBEDDING VALIDATION TEST")
    print(f"{'='*70}")
    print("\nThis test compares CLAP embeddings vs PyAnnote diarization")
    print("to see if CLAP can improve speaker clustering.")
    print(f"{'='*70}\n")
    
    # Get audio file
    if len(sys.argv) < 2:
        print("❌ Usage: python scripts/test_clap_clustering.py <audio_file.wav>")
        print("\nExample:")
        print("  python scripts/test_clap_clustering.py L:/test_audio/noisy_meeting.wav")
        sys.exit(1)
    
    audio_path = sys.argv[1]
    
    if not Path(audio_path).exists():
        print(f"❌ Audio file not found: {audio_path}")
        sys.exit(1)
    
    # Run validation
    try:
        # Step 1: Extract CLAP embeddings
        embeddings, timestamps = extract_clap_chunks(audio_path)
        
        if len(embeddings) == 0:
            print("❌ No CLAP embeddings extracted!")
            sys.exit(1)
        
        # Step 2: Cluster CLAP embeddings
        clap_labels, num_speakers = cluster_clap_embeddings(embeddings)
        
        # Step 3: Run PyAnnote baseline
        diarization, speakers, segments = run_pyannote_diarization(audio_path)
        
        if diarization is None:
            print("⚠️  PyAnnote failed, skipping comparison")
            return
        
        # Step 4: Compare results
        comparison = compare_results(clap_labels, timestamps, segments)
        
        # Step 5: Visualize
        output_dir = Path(__file__).parent.parent / "data" / "validation"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"clap_vs_pyannote_{Path(audio_path).stem}.png"
        
        visualize_comparison(clap_labels, timestamps, segments, str(output_path))
        
        # Final summary
        print(f"\n{'='*70}")
        print("✅ VALIDATION COMPLETE!")
        print(f"{'='*70}")
        print("\nSummary:")
        print(f"  Audio: {Path(audio_path).name}")
        print(f"  CLAP speakers: {comparison['clap_speakers']}")
        print(f"  PyAnnote speakers: {comparison['pyannote_speakers']}")
        print(f"  Agreement: {comparison['coverage']:.1f}%")
        print(f"\nVisualization saved to:")
        print(f"  {output_path}")
        print(f"\n{'='*70}")
        
        # Decision guidance
        print("\n🎯 WHAT THIS MEANS:")
        print(f"{'='*70}")
        
        speaker_diff = abs(comparison['clap_speakers'] - comparison['pyannote_speakers'])
        
        if speaker_diff == 0 and comparison['coverage'] > 95:
            print("✅ CLAP and PyAnnote agree closely (>95% agreement)")
            print("   → Current pipeline is optimal!")
            print("   → No need for Phase 2 integration")
        elif speaker_diff <= 1 and comparison['coverage'] > 80:
            print("⚠️  CLAP shows similar results to PyAnnote (80-95% agreement)")
            print("   → CLAP may offer marginal improvement")
            print("   → Consider Phase 2 if accuracy critical")
        else:
            print("🎯 CLAP shows different patterns than PyAnnote!")
            print(f"   → Speaker difference: {speaker_diff}")
            print(f"   → Agreement: {comparison['coverage']:.1f}%")
            print("   → ✨ PROCEED TO PHASE 2! CLAP may improve accuracy!")
        
        print(f"{'='*70}\n")
    
    except Exception as e:
        print(f"\n❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
