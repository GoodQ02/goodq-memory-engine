"""
GoodQ4All GPU Pipeline Optimizer
Monitors and tunes GPU memory allocation for optimal performance
"""

import subprocess
import time
import json
import os
import re
from pathlib import Path
from datetime import datetime
import psutil

class GPUOptimizer:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.log_dir = self.base_dir / "logs" / "gpu_optimization"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Step-specific GPU memory configurations (as fractions of total VRAM)
        self.gpu_configs = {
            "scene_detect": {
                "fraction": 0.15,  # 15% - lightweight OpenCV-based
                "device": "0",
                "priority": "low"
            },
            "audio_transcribe": {
                "fraction": 0.25,  # 25% - Whisper medium model
                "device": "0",
                "priority": "high"
            },
            "audio_diarize": {
                "fraction": 0.35,  # 35% - PyAnnote with embeddings
                "device": "0",
                "priority": "high"
            },
            "face_embed": {
                "fraction": 0.20,  # 20% - FaceNet embeddings
                "device": "0",
                "priority": "medium"
            },
            "emotion_classify": {
                "fraction": 0.20,  # 20% - Emotion CNN
                "device": "0",
                "priority": "medium"
            },
            "text_embed": {
                "fraction": 0.15,  # 15% - Sentence transformers
                "device": "0",
                "priority": "medium"
            },
            "clip_embed": {
                "fraction": 0.25,  # 25% - CLIP ViT model
                "device": "0",
                "priority": "medium"
            },
            "dino_embed": {
                "fraction": 0.25,  # 25% - DINOv2 model
                "device": "0",
                "priority": "medium"
            },
            "object_detect": {
                "fraction": 0.25,  # 25% - YOLOv8 or similar
                "device": "0",
                "priority": "medium"
            }
        }
        
        self.test_results = []
        
    def get_gpu_stats(self):
        """Get current GPU memory usage via nvidia-smi"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,memory.free,utilization.gpu,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True
            )
            
            values = result.stdout.strip().split(", ")
            return {
                "memory_used_mb": int(values[0]),
                "memory_total_mb": int(values[1]),
                "memory_free_mb": int(values[2]),
                "gpu_utilization": int(values[3]),
                "temperature": int(values[4]),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"[FAIL] Failed to get GPU stats: {e}")
            return None
    
    def get_process_gpu_usage(self):
        """Get GPU memory usage per process"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                check=True
            )
            
            processes = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(", ")
                    if len(parts) == 3:
                        processes.append({
                            "pid": int(parts[0]),
                            "name": parts[1],
                            "memory_mb": int(parts[2])
                        })
            return processes
        except Exception as e:
            print(f"[FAIL] Failed to get process GPU usage: {e}")
            return []
    
    def generate_gpu_config_file(self, step_name, test_run=1):
        """Generate GPU configuration for a specific step"""
        config = self.gpu_configs.get(step_name, {"fraction": 0.20, "device": "0"})
        
        gpu_config_content = f"""# GPU Configuration for {step_name} - Test Run {test_run}
# Generated: {datetime.now().isoformat()}

import os
import torch

# Set visible GPU device
os.environ["CUDA_VISIBLE_DEVICES"] = "{config['device']}"

# Configure PyTorch memory allocation
if torch.cuda.is_available():
    # Set memory fraction
    torch.cuda.set_per_process_memory_fraction({config['fraction']}, 0)
    
    # Enable TF32 for better performance on Ampere+ GPUs
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    
    # Optimize CUDA settings
    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.enabled = True
    
    # Clear cache before starting
    torch.cuda.empty_cache()
    
    print(f"[SYMBOL] GPU configured: Device {{config['device']}}, Memory fraction: {{config['fraction']}}")
    print(f"[SYMBOL] Available VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f}} GB")
    print(f"[SYMBOL] Allocated limit: {{torch.cuda.get_device_properties(0).total_memory * {config['fraction']} / 1024**3:.2f}} GB")
else:
    print("[SYMBOL] CUDA not available - using CPU")
"""
        
        # Save to step's env directory
        env_dir = self.base_dir / "envs" / step_name
        if env_dir.exists():
            config_file = env_dir / "gpu_config.py"
            config_file.write_text(gpu_config_content)
            print(f"[SYMBOL] Generated GPU config for {step_name}: {config['fraction']*100:.0f}% VRAM")
            return config_file
        else:
            print(f"[SYMBOL] Environment directory not found: {env_dir}")
            return None
    
    def monitor_pipeline_step(self, step_name, duration=60, interval=2):
        """Monitor GPU usage during a pipeline step"""
        print(f"\n{'='*80}")
        print(f"Monitoring GPU usage for: {step_name}")
        print(f"Duration: {duration}s, Interval: {interval}s")
        print(f"{'='*80}\n")
        
        samples = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            stats = self.get_gpu_stats()
            processes = self.get_process_gpu_usage()
            
            if stats:
                sample = {
                    "step": step_name,
                    "elapsed": time.time() - start_time,
                    **stats,
                    "processes": processes
                }
                samples.append(sample)
                
                print(f"[{sample['elapsed']:6.1f}s] "
                      f"VRAM: {stats['memory_used_mb']:5d}/{stats['memory_total_mb']:5d} MB "
                      f"({stats['memory_used_mb']/stats['memory_total_mb']*100:5.1f}%) | "
                      f"GPU: {stats['gpu_utilization']:3d}% | "
                      f"Temp: {stats['temperature']:2d}°C | "
                      f"Processes: {len(processes)}")
            
            time.sleep(interval)
        
        return self.analyze_samples(step_name, samples)
    
    def analyze_samples(self, step_name, samples):
        """Analyze monitoring samples and provide recommendations"""
        if not samples:
            return None
        
        # Calculate statistics
        mem_used = [s['memory_used_mb'] for s in samples]
        gpu_util = [s['gpu_utilization'] for s in samples]
        temps = [s['temperature'] for s in samples]
        
        analysis = {
            "step": step_name,
            "timestamp": datetime.now().isoformat(),
            "samples_count": len(samples),
            "memory": {
                "avg_mb": sum(mem_used) / len(mem_used),
                "peak_mb": max(mem_used),
                "min_mb": min(mem_used),
                "avg_percent": (sum(mem_used) / len(mem_used)) / samples[0]['memory_total_mb'] * 100,
                "peak_percent": max(mem_used) / samples[0]['memory_total_mb'] * 100
            },
            "utilization": {
                "avg": sum(gpu_util) / len(gpu_util),
                "peak": max(gpu_util),
                "min": min(gpu_util)
            },
            "temperature": {
                "avg": sum(temps) / len(temps),
                "peak": max(temps)
            }
        }
        
        # Generate recommendation
        current_fraction = self.gpu_configs.get(step_name, {}).get("fraction", 0.20)
        peak_percent = analysis['memory']['peak_percent']
        
        if peak_percent < current_fraction * 100 * 0.6:
            # Using less than 60% of allocated - can reduce
            recommended_fraction = round(peak_percent / 100 * 1.2, 2)  # 120% of peak usage
            recommendation = "REDUCE"
        elif peak_percent > current_fraction * 100 * 0.9:
            # Using more than 90% of allocated - should increase
            recommended_fraction = round(peak_percent / 100 * 1.2, 2)  # 120% of peak usage
            recommendation = "INCREASE"
        else:
            # Goldilocks zone
            recommended_fraction = current_fraction
            recommendation = "OPTIMAL"
        
        analysis['recommendation'] = {
            "action": recommendation,
            "current_fraction": current_fraction,
            "recommended_fraction": recommended_fraction,
            "reason": f"Peak usage: {peak_percent:.1f}% of total, {peak_percent/current_fraction/100:.0f}% of allocated"
        }
        
        return analysis
    
    def print_analysis(self, analysis):
        """Pretty print analysis results"""
        if not analysis:
            return
        
        print(f"\n{'='*80}")
        print(f"Analysis: {analysis['step']}")
        print(f"{'='*80}")
        print(f"Memory:")
        print(f"  Average: {analysis['memory']['avg_mb']:.0f} MB ({analysis['memory']['avg_percent']:.1f}%)")
        print(f"  Peak:    {analysis['memory']['peak_mb']:.0f} MB ({analysis['memory']['peak_percent']:.1f}%)")
        print(f"  Min:     {analysis['memory']['min_mb']:.0f} MB")
        print(f"\nGPU Utilization:")
        print(f"  Average: {analysis['utilization']['avg']:.1f}%")
        print(f"  Peak:    {analysis['utilization']['peak']}%")
        print(f"\nTemperature:")
        print(f"  Average: {analysis['temperature']['avg']:.1f}°C")
        print(f"  Peak:    {analysis['temperature']['peak']}°C")
        print(f"\n{'─'*80}")
        rec = analysis['recommendation']
        print(f"Recommendation: {rec['action']}")
        print(f"  Current allocation:     {rec['current_fraction']*100:.0f}%")
        print(f"  Recommended allocation: {rec['recommended_fraction']*100:.0f}%")
        print(f"  Reason: {rec['reason']}")
        print(f"{'='*80}\n")
    
    def save_test_results(self, test_number):
        """Save test results to JSON"""
        if not self.test_results:
            return
        
        filename = self.log_dir / f"gpu_test_{test_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"[SYMBOL] Test results saved: {filename}")
    
    def update_gpu_configs(self, analyses):
        """Update GPU configurations based on analysis results"""
        updated = []
        
        for analysis in analyses:
            step = analysis['step']
            rec = analysis['recommendation']
            
            if rec['action'] != "OPTIMAL":
                old_fraction = self.gpu_configs[step]['fraction']
                new_fraction = rec['recommended_fraction']
                self.gpu_configs[step]['fraction'] = new_fraction
                updated.append({
                    "step": step,
                    "old": old_fraction,
                    "new": new_fraction,
                    "action": rec['action']
                })
                print(f"[SYMBOL] Updated {step}: {old_fraction*100:.0f}% → {new_fraction*100:.0f}%")
        
        return updated
    
    def generate_all_configs(self):
        """Generate GPU config files for all steps"""
        print(f"\n{'='*80}")
        print("Generating GPU Configuration Files")
        print(f"{'='*80}\n")
        
        for step_name in self.gpu_configs.keys():
            self.generate_gpu_config_file(step_name)
        
        print(f"\n[SYMBOL] All GPU configurations generated")
    
    def run_optimization_cycle(self, video_path, test_number=1):
        """Run a full optimization cycle"""
        print(f"\n{'╔'+'═'*78+'╗'}")
        print(f"║{f' GPU OPTIMIZATION TEST RUN #{test_number} ':^78}║")
        print(f"{'╚'+'═'*78+'╝'}\n")
        print(f"Video: {video_path}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Generate configs for this test
        self.generate_all_configs()
        
        # Start pipeline and monitor
        # (This would integrate with your actual pipeline launch)
        print(f"\n[SYMBOL] Note: Actual pipeline execution to be integrated")
        print(f"   For now, this monitors any running GPU processes\n")
        
        # Monitor for a period
        stats = self.get_gpu_stats()
        if stats:
            print(f"Initial GPU state:")
            print(f"  VRAM: {stats['memory_used_mb']} / {stats['memory_total_mb']} MB")
            print(f"  Free: {stats['memory_free_mb']} MB ({stats['memory_free_mb']/stats['memory_total_mb']*100:.1f}%)")
            print(f"  Temp: {stats['temperature']}°C\n")


if __name__ == "__main__":
    import sys
    
    optimizer = GPUOptimizer()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "generate":
            # Just generate config files
            optimizer.generate_all_configs()
        elif sys.argv[1] == "monitor":
            # Monitor current GPU usage
            step_name = sys.argv[2] if len(sys.argv) > 2 else "general"
            duration = int(sys.argv[3]) if len(sys.argv) > 3 else 60
            analysis = optimizer.monitor_pipeline_step(step_name, duration=duration)
            if analysis:
                optimizer.print_analysis(analysis)
        elif sys.argv[1] == "stats":
            # Show current GPU stats
            stats = optimizer.get_gpu_stats()
            processes = optimizer.get_process_gpu_usage()
            print(f"\n{'='*80}")
            print(f"Current GPU Status")
            print(f"{'='*80}")
            print(json.dumps(stats, indent=2))
            print(f"\nRunning processes:")
            print(json.dumps(processes, indent=2))
    else:
        # Default: show stats
        optimizer.generate_all_configs()
        stats = optimizer.get_gpu_stats()
        if stats:
            print(f"\n{'='*80}")
            print(f"GPU Ready for Optimization")
            print(f"{'='*80}")
            print(f"Total VRAM: {stats['memory_total_mb']} MB ({stats['memory_total_mb']/1024:.1f} GB)")
            print(f"Used:       {stats['memory_used_mb']} MB ({stats['memory_used_mb']/stats['memory_total_mb']*100:.1f}%)")
            print(f"Free:       {stats['memory_free_mb']} MB ({stats['memory_free_mb']/1024:.1f} GB)")
            print(f"{'='*80}\n")
            print(f"Usage:")
            print(f"  python scripts/gpu_pipeline_optimizer.py generate  - Generate GPU configs")
            print(f"  python scripts/gpu_pipeline_optimizer.py monitor <step> <duration>  - Monitor step")
            print(f"  python scripts/gpu_pipeline_optimizer.py stats  - Show GPU stats")
