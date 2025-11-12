"""
Real-Time Audio GPU Monitor
Monitors GPU usage during audio processing in real-time
"""

import subprocess
import time
import threading
import sys
import os
from datetime import datetime
from pathlib import Path

class AudioGPUMonitor:
    """Real-time GPU monitoring for audio pipeline"""
    
    def __init__(self, sample_interval=2.0):
        self.sample_interval = sample_interval
        self.monitoring = False
        self.samples = []
        self.monitor_thread = None
        
    def get_gpu_stats(self):
        """Get current GPU stats via nvidia-smi"""
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
            if len(values) >= 5:
                return {
                    "timestamp": time.time(),
                    "memory_used_mb": float(values[0]),
                    "memory_total_mb": float(values[1]),
                    "gpu_util_pct": float(values[2]),
                    "temp_c": float(values[3]),
                    "power_w": float(values[4]),
                }
        except Exception as e:
            pass
        
        return None
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        print("[Monitor] GPU monitoring started")
        
        while self.monitoring:
            stats = self.get_gpu_stats()
            if stats:
                self.samples.append(stats)
                
                # Print live update
                mem_gb = stats["memory_used_mb"] / 1024
                total_gb = stats["memory_total_mb"] / 1024
                util = stats["gpu_util_pct"]
                temp = stats["temp_c"]
                power = stats["power_w"]
                
                print(f"\r[Monitor] VRAM: {mem_gb:.1f}/{total_gb:.1f}GB | "
                      f"GPU: {util:.0f}% | "
                      f"Temp: {temp:.0f}°C | "
                      f"Power: {power:.0f}W", end="", flush=True)
            
            time.sleep(self.sample_interval)
        
        print("\n[Monitor] GPU monitoring stopped")
    
    def start(self):
        """Start monitoring"""
        if self.monitoring:
            print("[Monitor] Already monitoring")
            return
        
        self.monitoring = True
        self.samples = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """Stop monitoring"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def get_summary(self):
        """Get summary statistics"""
        if not self.samples:
            return None
        
        mem_used = [s["memory_used_mb"] / 1024 for s in self.samples]
        gpu_util = [s["gpu_util_pct"] for s in self.samples]
        temps = [s["temp_c"] for s in self.samples]
        power = [s["power_w"] for s in self.samples]
        
        return {
            "duration_seconds": self.samples[-1]["timestamp"] - self.samples[0]["timestamp"],
            "sample_count": len(self.samples),
            "vram_avg_gb": sum(mem_used) / len(mem_used),
            "vram_peak_gb": max(mem_used),
            "vram_min_gb": min(mem_used),
            "gpu_util_avg_pct": sum(gpu_util) / len(gpu_util),
            "gpu_util_peak_pct": max(gpu_util),
            "temp_avg_c": sum(temps) / len(temps),
            "temp_peak_c": max(temps),
            "power_avg_w": sum(power) / len(power),
            "power_peak_w": max(power),
        }
    
    def print_summary(self):
        """Print summary statistics"""
        summary = self.get_summary()
        
        if not summary:
            print("[Monitor] No data collected")
            return
        
        print("\n" + "="*80)
        print("GPU Monitoring Summary")
        print("="*80)
        print(f"  Duration: {summary['duration_seconds']:.1f}s")
        print(f"  Samples: {summary['sample_count']}")
        print(f"\n  VRAM Usage:")
        print(f"    Average: {summary['vram_avg_gb']:.2f} GB")
        print(f"    Peak: {summary['vram_peak_gb']:.2f} GB")
        print(f"    Min: {summary['vram_min_gb']:.2f} GB")
        print(f"\n  GPU Utilization:")
        print(f"    Average: {summary['gpu_util_avg_pct']:.1f}%")
        print(f"    Peak: {summary['gpu_util_peak_pct']:.1f}%")
        print(f"\n  Temperature:")
        print(f"    Average: {summary['temp_avg_c']:.1f}°C")
        print(f"    Peak: {summary['temp_peak_c']:.1f}°C")
        print(f"\n  Power Draw:")
        print(f"    Average: {summary['power_avg_w']:.1f}W")
        print(f"    Peak: {summary['power_peak_w']:.1f}W")
        print("="*80 + "\n")
    
    def save_report(self, filepath=None):
        """Save monitoring data to file"""
        if not self.samples:
            print("[Monitor] No data to save")
            return
        
        if filepath is None:
            report_dir = Path("L:/goodq4all/logs/gpu_monitoring")
            report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = report_dir / f"gpu_monitor_{timestamp}.csv"
        
        with open(filepath, 'w') as f:
            # Write header
            f.write("timestamp,memory_used_mb,memory_total_mb,gpu_util_pct,temp_c,power_w\n")
            
            # Write samples
            for sample in self.samples:
                f.write(f"{sample['timestamp']:.3f},"
                       f"{sample['memory_used_mb']:.1f},"
                       f"{sample['memory_total_mb']:.1f},"
                       f"{sample['gpu_util_pct']:.1f},"
                       f"{sample['temp_c']:.1f},"
                       f"{sample['power_w']:.1f}\n")
        
        print(f"[Monitor] Data saved to: {filepath}")


def main():
    """Main monitoring function"""
    print("\n" + "="*80)
    print("Audio GPU Real-Time Monitor")
    print("="*80 + "\n")
    print("This will monitor GPU usage in real-time.")
    print("Press Ctrl+C to stop monitoring and view summary.\n")
    
    monitor = AudioGPUMonitor(sample_interval=1.0)
    
    try:
        monitor.start()
        
        # Keep monitoring until interrupted
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n[Monitor] Stopping...")
        monitor.stop()
        monitor.print_summary()
        monitor.save_report()
        print("\nDone!")


if __name__ == "__main__":
    main()
