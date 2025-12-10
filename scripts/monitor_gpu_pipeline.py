"""
Real-time GPU Pipeline Monitor
Monitors GPU usage during actual pipeline execution
"""

import subprocess
import time
import json
import threading
from datetime import datetime
from pathlib import Path
import re

class RealTimeGPUMonitor:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.monitoring = False
        self.samples = []
        self.current_step = "initialization"
        self.step_patterns = {
            "scene_detect": r"scene.detect|video_scene",
            "audio_transcribe": r"audio.transcribe|whisper|[Tt]ranscrib",
            "audio_diarize": r"audio.diarize|pyannote|[Dd]iariz",
            "face_embed": r"face.embed|facenet",
            "emotion_classify": r"emotion.classify",
            "text_embed": r"text.embed|sentence",
            "clip_embed": r"clip.embed|image_embed_clip",
            "dino_embed": r"dino.embed|image_embed_dino",
            "object_detect": r"object.detect|yolo",
            "image_caption": r"caption",
            "audio_emotion": r"audio.emotion|audio_emotion",
            "image_ocr": r"ocr",
        }
        
        self.step_samples = {}  # Samples grouped by step
        
    def get_gpu_stats(self):
        """Get current GPU stats"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            
            values = result.stdout.strip().split(", ")
            return {
                "memory_used_mb": int(values[0]),
                "memory_total_mb": int(values[1]),
                "gpu_util": int(values[2]),
                "temperature": int(values[3]),
                "power_draw": float(values[4]),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return None
    
    def detect_step_from_log(self, line):
        """Detect which pipeline step is currently running"""
        for step, pattern in self.step_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                return step
        return None
    
    def monitor_thread(self, interval=2):
        """Background thread that samples GPU stats"""
        print(f"[SEARCH] GPU Monitor started (sampling every {interval}s)")
        
        while self.monitoring:
            stats = self.get_gpu_stats()
            if stats:
                sample = {
                    "step": self.current_step,
                    "elapsed": time.time() - self.start_time,
                    **stats
                }
                self.samples.append(sample)
                
                # Group by step
                if self.current_step not in self.step_samples:
                    self.step_samples[self.current_step] = []
                self.step_samples[self.current_step].append(sample)
                
                # Print current stats
                print(f"\r[{sample['elapsed']:6.1f}s] "
                      f"{self.current_step:20s} | "
                      f"VRAM: {stats['memory_used_mb']:5d}/{stats['memory_total_mb']:5d} MB "
                      f"({stats['memory_used_mb']/stats['memory_total_mb']*100:5.1f}%) | "
                      f"GPU: {stats['gpu_util']:3d}% | "
                      f"Temp: {stats['temperature']:2d}°C | "
                      f"Power: {stats['power_draw']:5.1f}W", end='', flush=True)
            
            time.sleep(interval)
    
    def start_monitoring(self):
        """Start monitoring in background thread"""
        self.monitoring = True
        self.start_time = time.time()
        self.monitor_thread_obj = threading.Thread(target=self.monitor_thread, daemon=True)
        self.monitor_thread_obj.start()
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread_obj'):
            self.monitor_thread_obj.join(timeout=5)
        print("\n[SYMBOL] GPU Monitor stopped")
    
    def update_current_step(self, step_name):
        """Update the current step being monitored"""
        if step_name != self.current_step:
            old_step = self.current_step
            self.current_step = step_name
            print(f"\n\n[SYNC] Step changed: {old_step} → {step_name}")
    
    def analyze_step_usage(self, step_name):
        """Analyze GPU usage for a specific step"""
        if step_name not in self.step_samples or not self.step_samples[step_name]:
            return None
        
        samples = self.step_samples[step_name]
        mem_used = [s['memory_used_mb'] for s in samples]
        gpu_util = [s['gpu_util'] for s in samples]
        temps = [s['temperature'] for s in samples]
        power = [s['power_draw'] for s in samples]
        
        return {
            "step": step_name,
            "sample_count": len(samples),
            "duration_seconds": samples[-1]['elapsed'] - samples[0]['elapsed'] if len(samples) > 1 else 0,
            "memory": {
                "avg_mb": sum(mem_used) / len(mem_used),
                "peak_mb": max(mem_used),
                "min_mb": min(mem_used),
                "avg_percent": (sum(mem_used) / len(mem_used)) / samples[0]['memory_total_mb'] * 100,
                "peak_percent": max(mem_used) / samples[0]['memory_total_mb'] * 100,
            },
            "gpu_utilization": {
                "avg": sum(gpu_util) / len(gpu_util),
                "peak": max(gpu_util),
                "min": min(gpu_util),
            },
            "temperature": {
                "avg": sum(temps) / len(temps),
                "peak": max(temps),
            },
            "power": {
                "avg_watts": sum(power) / len(power),
                "peak_watts": max(power),
            }
        }
    
    def generate_report(self):
        """Generate comprehensive GPU usage report"""
        print("\n\n" + "="*80)
        print("GPU Usage Analysis Report")
        print("="*80)
        
        if not self.samples:
            print("No samples collected")
            return None
        
        total_duration = self.samples[-1]['elapsed'] if self.samples else 0
        
        print(f"\nTotal Duration: {total_duration:.1f}s")
        print(f"Total Samples: {len(self.samples)}")
        print(f"Steps Monitored: {len(self.step_samples)}")
        
        # Analyze each step
        step_analyses = {}
        for step_name in self.step_samples.keys():
            if step_name == "initialization":
                continue
            
            analysis = self.analyze_step_usage(step_name)
            if analysis and analysis['sample_count'] > 0:
                step_analyses[step_name] = analysis
                
                print(f"\n{'─'*80}")
                print(f"Step: {step_name}")
                print(f"{'─'*80}")
                print(f"Duration: {analysis['duration_seconds']:.1f}s")
                print(f"Samples: {analysis['sample_count']}")
                print(f"\nMemory Usage:")
                print(f"  Average: {analysis['memory']['avg_mb']:.0f} MB ({analysis['memory']['avg_percent']:.1f}%)")
                print(f"  Peak:    {analysis['memory']['peak_mb']:.0f} MB ({analysis['memory']['peak_percent']:.1f}%)")
                print(f"\nGPU Utilization:")
                print(f"  Average: {analysis['gpu_utilization']['avg']:.1f}%")
                print(f"  Peak:    {analysis['gpu_utilization']['peak']}%")
                print(f"\nTemperature:")
                print(f"  Average: {analysis['temperature']['avg']:.1f}°C")
                print(f"  Peak:    {analysis['temperature']['peak']}°C")
                print(f"\nPower Draw:")
                print(f"  Average: {analysis['power']['avg_watts']:.1f}W")
                print(f"  Peak:    {analysis['power']['peak_watts']:.1f}W")
        
        print(f"\n{'='*80}")
        
        # Save detailed report
        report_file = self.base_dir / "logs" / "gpu_optimization" / f"monitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_duration_seconds": total_duration,
            "total_samples": len(self.samples),
            "step_analyses": step_analyses,
            "raw_samples": self.samples
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        print(f"\n[SYMBOL] Detailed report saved: {report_file}")
        
        return step_analyses
    
    def run_pipeline_with_monitoring(self):
        """Run the pipeline with real-time GPU monitoring"""
        print("="*80)
        print("GPU-Monitored Pipeline Execution")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Start GPU monitoring
        self.start_monitoring()
        
        # Start the watchdog/pipeline
        watchdog_cmd = [
            "conda", "run", "-n", "goodq_zenml", "--no-capture-output",
            "python", str(self.base_dir / "scripts" / "watchdog_ingest.py")
        ]
        
        print("[LAUNCH] Starting pipeline...")
        process = subprocess.Popen(
            watchdog_cmd,
            cwd=str(self.base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print(f"[SYMBOL] Pipeline started (PID: {process.pid})\n")
        
        # Monitor output and detect steps
        try:
            while process.poll() is None:
                line = process.stdout.readline()
                if line:
                    # Detect step changes
                    detected_step = self.detect_step_from_log(line)
                    if detected_step:
                        self.update_current_step(detected_step)
                    
                    # Print the output line (but on new line after GPU stats)
                    if line.strip():
                        print(f"\n  {line.rstrip()}", end='')
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\n[SYMBOL] Interrupted by user")
            process.terminate()
        
        finally:
            # Stop monitoring
            self.stop_monitoring()
            
            # Wait for process to finish
            try:
                process.wait(timeout=10)
            except:
                process.kill()
        
        # Generate report
        print("\n\n[STATS] Generating usage report...")
        analyses = self.generate_report()
        
        return analyses


if __name__ == "__main__":
    monitor = RealTimeGPUMonitor()
    monitor.run_pipeline_with_monitoring()
