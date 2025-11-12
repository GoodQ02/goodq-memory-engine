"""
Full GPU Pipeline Optimization Test Suite
Runs multiple iterations, monitors GPU usage, and tunes allocations
"""

import subprocess
import time
import json
import sys
from pathlib import Path
from datetime import datetime
from gpu_pipeline_optimizer import GPUOptimizer

class PipelineOptimizationRunner:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.optimizer = GPUOptimizer(base_dir)
        self.test_video = None
        self.test_iterations = 5
        self.all_test_results = []
        
    def find_test_video(self):
        """Find a suitable test video"""
        # Check for sample video
        sample_paths = [
            self.base_dir / "import_inbox" / "sample.mp4",
            self.base_dir / "test_input" / "sample.mp4",
            Path("L:/_DATA/FAMILY_FEAST")
        ]
        
        for path in sample_paths:
            if path.exists():
                if path.is_file():
                    return path
                elif path.is_dir():
                    # Find first MP4 in directory
                    videos = list(path.glob("*.mp4"))
                    if videos:
                        return videos[0]
        
        return None
    
    def cleanup_processing(self):
        """Clean up any existing processing state"""
        print("\n🧹 Cleaning up previous processing state...")
        
        # Clear processing directory
        processing_dir = self.base_dir / "data" / "processing"
        if processing_dir.exists():
            import shutil
            for item in processing_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                    print(f"  ✓ Removed: {item.name}")
        
        # Clear GPU cache
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                print("  ✓ Cleared CUDA cache")
        except:
            pass
        
        print("✓ Cleanup complete\n")
    
    def wait_for_gpu_idle(self, max_wait=30):
        """Wait for GPU to be idle"""
        print("⏳ Waiting for GPU to be idle...")
        start = time.time()
        
        while time.time() - start < max_wait:
            stats = self.optimizer.get_gpu_stats()
            if stats and stats['gpu_utilization'] < 10:
                print(f"✓ GPU idle ({stats['gpu_utilization']}% utilization)")
                time.sleep(2)  # Extra buffer
                return True
            time.sleep(1)
        
        print("⚠ GPU did not become idle, continuing anyway...")
        return False
    
    def run_single_test(self, test_number, video_path):
        """Run a single pipeline test with monitoring"""
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{f' TEST RUN {test_number}/{self.test_iterations} ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        
        # Generate GPU configs for this test
        self.optimizer.generate_all_configs()
        
        # Clean up before test
        self.cleanup_processing()
        self.wait_for_gpu_idle()
        
        # Start baseline monitoring
        print("📊 Capturing baseline GPU state...")
        baseline = self.optimizer.get_gpu_stats()
        
        # Copy video to import inbox
        import shutil
        inbox = self.base_dir / "import_inbox"
        inbox.mkdir(exist_ok=True)
        
        # Clear inbox first
        for item in inbox.glob("*"):
            if item.is_file():
                item.unlink()
        
        test_video_name = f"test_{test_number}_{video_path.name}"
        dest = inbox / test_video_name
        
        print(f"📁 Copying test video: {video_path.name}")
        print(f"   → {dest}")
        shutil.copy2(video_path, dest)
        
        print(f"✓ Video ready for processing\n")
        
        # Start watchdog (pipeline)
        print("🚀 Starting pipeline...")
        watchdog_cmd = [
            "conda", "run", "-n", "goodq_zenml", "--no-capture-output",
            "python", str(self.base_dir / "scripts" / "watchdog_ingest.py")
        ]
        
        # Start process in background
        process = subprocess.Popen(
            watchdog_cmd,
            cwd=str(self.base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print(f"✓ Pipeline started (PID: {process.pid})")
        print(f"⏱ Monitoring GPU usage...\n")
        
        # Monitor GPU usage throughout processing
        step_analyses = {}
        current_step = "initialization"
        samples = []
        
        start_time = time.time()
        max_runtime = 600  # 10 minutes max
        sample_interval = 3  # Sample every 3 seconds
        last_sample = 0
        
        step_patterns = {
            "scene_detect": r"scene.detect",
            "audio_transcribe": r"audio.transcribe|whisper",
            "audio_diarize": r"audio.diarize|pyannote",
            "face_embed": r"face.embed|facenet",
            "emotion_classify": r"emotion.classify",
            "text_embed": r"text.embed|sentence",
            "clip_embed": r"clip.embed",
            "dino_embed": r"dino.embed",
            "object_detect": r"object.detect|yolo"
        }
        
        try:
            while process.poll() is None and time.time() - start_time < max_runtime:
                # Read output to detect current step
                if process.stdout:
                    line = process.stdout.readline()
                    if line:
                        print(f"  {line.rstrip()}")
                        
                        # Detect which step is running
                        import re
                        for step, pattern in step_patterns.items():
                            if re.search(pattern, line, re.IGNORECASE):
                                if step != current_step:
                                    # Save previous step's samples
                                    if samples and current_step != "initialization":
                                        analysis = self.optimizer.analyze_samples(current_step, samples)
                                        if analysis:
                                            step_analyses[current_step] = analysis
                                            self.optimizer.print_analysis(analysis)
                                    
                                    # Start new step
                                    current_step = step
                                    samples = []
                                    print(f"\n🔄 Step detected: {step}\n")
                                break
                
                # Sample GPU at intervals
                if time.time() - last_sample >= sample_interval:
                    stats = self.optimizer.get_gpu_stats()
                    processes = self.optimizer.get_process_gpu_usage()
                    
                    if stats:
                        sample = {
                            "step": current_step,
                            "elapsed": time.time() - start_time,
                            **stats,
                            "processes": processes
                        }
                        samples.append(sample)
                        
                        print(f"[{sample['elapsed']:6.1f}s] "
                              f"{current_step:20s} | "
                              f"VRAM: {stats['memory_used_mb']:5d}/{stats['memory_total_mb']:5d} MB "
                              f"({stats['memory_used_mb']/stats['memory_total_mb']*100:5.1f}%) | "
                              f"GPU: {stats['gpu_utilization']:3d}% | "
                              f"Temp: {stats['temperature']:2d}°C")
                    
                    last_sample = time.time()
                
                time.sleep(0.5)
            
            # Analyze final step
            if samples and current_step != "initialization":
                analysis = self.optimizer.analyze_samples(current_step, samples)
                if analysis:
                    step_analyses[current_step] = analysis
                    self.optimizer.print_analysis(analysis)
            
        except KeyboardInterrupt:
            print("\n⚠ Test interrupted by user")
        finally:
            # Stop process if still running
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except:
                    process.kill()
        
        elapsed = time.time() - start_time
        
        # Compile test results
        test_result = {
            "test_number": test_number,
            "timestamp": datetime.now().isoformat(),
            "video": str(video_path),
            "duration_seconds": elapsed,
            "baseline": baseline,
            "step_analyses": step_analyses,
            "gpu_configs": dict(self.optimizer.gpu_configs)
        }
        
        self.all_test_results.append(test_result)
        
        print(f"\n{'='*80}")
        print(f"Test {test_number} Complete - Duration: {elapsed:.1f}s")
        print(f"Steps analyzed: {len(step_analyses)}")
        print(f"{'='*80}\n")
        
        return test_result
    
    def optimize_from_results(self):
        """Analyze all test results and optimize GPU allocations"""
        if not self.all_test_results:
            print("⚠ No test results to analyze")
            return
        
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{' OPTIMIZATION ANALYSIS ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        
        # Aggregate analyses by step
        step_aggregates = {}
        
        for test in self.all_test_results:
            for step, analysis in test['step_analyses'].items():
                if step not in step_aggregates:
                    step_aggregates[step] = []
                step_aggregates[step].append(analysis)
        
        # Calculate optimal configurations
        optimized_configs = {}
        
        for step, analyses in step_aggregates.items():
            peak_mems = [a['memory']['peak_percent'] for a in analyses]
            avg_utils = [a['utilization']['avg'] for a in analyses]
            
            avg_peak = sum(peak_mems) / len(peak_mems)
            max_peak = max(peak_mems)
            avg_util = sum(avg_utils) / len(avg_utils)
            
            # Optimal fraction = 120% of average peak usage
            optimal_fraction = round(max_peak / 100 * 1.2, 2)
            optimal_fraction = max(0.10, min(0.50, optimal_fraction))  # Clamp 10-50%
            
            optimized_configs[step] = {
                "fraction": optimal_fraction,
                "device": "0",
                "stats": {
                    "avg_peak_percent": avg_peak,
                    "max_peak_percent": max_peak,
                    "avg_utilization": avg_util,
                    "test_count": len(analyses)
                }
            }
            
            current = self.optimizer.gpu_configs.get(step, {}).get("fraction", 0.20)
            change = "➚" if optimal_fraction > current else "➘" if optimal_fraction < current else "="
            
            print(f"{step:20s}: {current*100:5.1f}% → {optimal_fraction*100:5.1f}% {change}  "
                  f"(peak: {max_peak:5.1f}%, util: {avg_util:5.1f}%)")
        
        # Update optimizer configs
        self.optimizer.gpu_configs.update(optimized_configs)
        
        # Save final optimized configs
        config_file = self.base_dir / "config" / "gpu_optimized.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(optimized_configs, f, indent=2)
        
        print(f"\n✓ Optimized configuration saved: {config_file}")
        
        return optimized_configs
    
    def run_full_optimization(self):
        """Run complete optimization suite"""
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{' GoodQ4All GPU Pipeline Optimization Suite ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Iterations: {self.test_iterations}")
        
        # Find test video
        self.test_video = self.find_test_video()
        if not self.test_video:
            print("\n❌ No test video found!")
            print("Please place a video in one of these locations:")
            print("  - L:/goodq4all/import_inbox/sample.mp4")
            print("  - L:/_DATA/FAMILY_FEAST/*.mp4")
            return False
        
        print(f"Test video: {self.test_video}")
        print(f"{'='*80}\n")
        
        # Run initial test
        for i in range(1, self.test_iterations + 1):
            test_result = self.run_single_test(i, self.test_video)
            
            # After each test (except last), optimize and regenerate configs
            if i < self.test_iterations:
                print(f"\n🔧 Optimizing configurations for next test...")
                analyses = list(test_result['step_analyses'].values())
                if analyses:
                    updates = self.optimizer.update_gpu_configs(analyses)
                    if updates:
                        print(f"✓ Updated {len(updates)} step configurations")
                    else:
                        print("✓ Configurations already optimal")
                
                # Wait before next test
                print(f"\n⏸ Waiting 30s before next test...\n")
                time.sleep(30)
        
        # Final optimization
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{' FINAL OPTIMIZATION ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        
        optimized = self.optimize_from_results()
        
        # Generate final GPU config files
        print(f"\n🔧 Generating optimized GPU configuration files...")
        self.optimizer.generate_all_configs()
        
        # Save comprehensive results
        results_file = self.base_dir / "logs" / "gpu_optimization" / f"full_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        
        final_results = {
            "timestamp": datetime.now().isoformat(),
            "test_video": str(self.test_video),
            "iterations": self.test_iterations,
            "test_results": self.all_test_results,
            "optimized_configs": optimized
        }
        
        with open(results_file, 'w') as f:
            json.dump(final_results, f, indent=2)
        
        print(f"\n✓ Complete results saved: {results_file}")
        
        # Print summary
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{' OPTIMIZATION COMPLETE ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        print(f"Total tests run: {len(self.all_test_results)}")
        print(f"Steps optimized: {len(optimized)}")
        print(f"Results saved: {results_file}")
        print(f"\n🎉 GPU pipeline is now optimized for production use!")
        print(f"\nNext steps:")
        print(f"  1. Review optimization results in: {results_file}")
        print(f"  2. GPU configs have been updated in each env directory")
        print(f"  3. Run production pipeline with optimized settings")
        print(f"{'='*80}\n")
        
        return True


if __name__ == "__main__":
    runner = PipelineOptimizationRunner()
    
    # Check for command line args
    if len(sys.argv) > 1:
        if sys.argv[1].isdigit():
            runner.test_iterations = int(sys.argv[1])
    
    success = runner.run_full_optimization()
    sys.exit(0 if success else 1)
