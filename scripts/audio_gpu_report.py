"""
Audio GPU Performance Report Generator
Analyzes GPU usage during audio processing and provides optimization recommendations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from steps.common.audio_gpu_optimizer import get_audio_gpu_optimizer
import json
from datetime import datetime
from pathlib import Path


def generate_report():
    """Generate comprehensive GPU performance report"""
    
    print("\n" + "="*80)
    print("Audio GPU Performance Report")
    print("="*80 + "\n")
    
    optimizer = get_audio_gpu_optimizer()
    
    # Get current GPU stats
    stats = optimizer.get_memory_stats()
    
    print("Current GPU Status:")
    print("-" * 80)
    print(f"  Device: {stats.get('device', 'unknown')}")
    
    if stats.get('available'):
        print(f"  Total VRAM: {stats.get('total_gb', 0):.2f} GB")
        print(f"  Allocated: {stats.get('allocated_gb', 0):.2f} GB")
        print(f"  Reserved: {stats.get('reserved_gb', 0):.2f} GB")
        print(f"  Free: {stats.get('free_gb', 0):.2f} GB")
        print(f"  Utilization: {stats.get('utilization', 0):.1f}%")
    else:
        print(f"  Status: Not available (CPU mode)")
    
    print()
    
    # Get performance report
    perf_report = optimizer.get_performance_report()
    
    if perf_report.get("status") == "ok":
        print("\nPerformance Metrics:")
        print("-" * 80)
        print(f"  Total samples: {perf_report.get('total_samples', 0)}")
        print(f"  Average realtime factor: {perf_report.get('overall_avg_realtime_factor', 0):.2f}x")
        print(f"  Average memory usage: {perf_report.get('overall_avg_memory_gb', 0):.2f} GB")
        print()
        
        # Per-step breakdown
        by_step = perf_report.get('by_step', {})
        if by_step:
            print("\nPer-Step Performance:")
            print("-" * 80)
            for step_name, step_stats in by_step.items():
                print(f"\n  {step_name}:")
                print(f"    Samples: {step_stats.get('count', 0)}")
                print(f"    Avg realtime: {step_stats.get('avg_realtime_factor', 0):.2f}x")
                print(f"    Avg processing time: {step_stats.get('avg_processing_time', 0):.1f}s")
        
        # Optimization suggestions
        suggestions = optimizer.optimize_for_next_run()
        if suggestions:
            print("\n\nOptimization Recommendations:")
            print("-" * 80)
            recommendation = suggestions.get("recommendation", "maintain")
            
            if recommendation == "increase":
                print("  ✅ GPU is underutilized - can increase memory allocation")
                print(f"     Recommended diarization: {suggestions.get('diarization', 0)*100:.0f}%")
                print(f"     Recommended transcription: {suggestions.get('transcription', 0)*100:.0f}%")
            elif recommendation == "decrease":
                print("  ⚠️  GPU near capacity - should decrease memory allocation")
                print(f"     Recommended diarization: {suggestions.get('diarization', 0)*100:.0f}%")
                print(f"     Recommended transcription: {suggestions.get('transcription', 0)*100:.0f}%")
            else:
                print("  ✅ GPU utilization is optimal - maintain current settings")
                print(f"     Current diarization: {suggestions.get('diarization', 0)*100:.0f}%")
                print(f"     Current transcription: {suggestions.get('transcription', 0)*100:.0f}%")
    
    else:
        print("\nPerformance Metrics: No data collected yet")
        print("  Run audio processing to collect performance data")
    
    print("\n" + "="*80)
    print()
    
    # Save report to file
    report_dir = Path("L:/goodq4all/logs/gpu_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = report_dir / f"audio_gpu_report_{timestamp}.json"
    
    report_data = {
        "timestamp": timestamp,
        "gpu_stats": stats,
        "performance": perf_report,
        "suggestions": suggestions if perf_report.get("status") == "ok" else {}
    }
    
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"Report saved to: {report_file}")
    print()


if __name__ == "__main__":
    generate_report()
