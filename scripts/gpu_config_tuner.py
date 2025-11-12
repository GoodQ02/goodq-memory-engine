"""
GPU Configuration Tuner
Interactive tool to adjust GPU memory allocations
"""

import json
from pathlib import Path

class GPUConfigTuner:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.config_file = self.base_dir / "steps" / "common" / "gpu_config.py"
        
        self.steps = {
            "video_scene_detect": 0.15,
            "audio_transcribe": 0.25,
            "audio_diarize": 0.35,
            "face_embed": 0.20,
            "emotion_classify": 0.20,
            "text_embed": 0.15,
            "image_embed_clip": 0.25,
            "image_embed_dino": 0.25,
            "object_detect": 0.25,
            "object_track_yolo": 0.25,
            "image_caption": 0.20,
            "audio_embed_clap": 0.20,
            "audio_emotion": 0.15,
            "image_ocr": 0.15,
            "llm_chat": 0.40,
        }
    
    def show_current_config(self):
        """Display current GPU allocations"""
        print("\n" + "="*80)
        print("Current GPU Memory Allocations")
        print("="*80)
        print(f"{'Step':<30} {'Allocation':<15} {'VRAM (16GB GPU)':<20}")
        print("-"*80)
        
        for step, fraction in sorted(self.steps.items()):
            vram_gb = fraction * 16
            print(f"{step:<30} {fraction*100:>6.1f}% {vram_gb:>10.2f} GB")
        
        print("="*80 + "\n")
    
    def adjust_step(self, step_name, new_fraction):
        """Adjust allocation for a specific step"""
        if step_name not in self.steps:
            print(f"❌ Unknown step: {step_name}")
            return False
        
        if not (0.05 <= new_fraction <= 0.80):
            print(f"❌ Fraction must be between 0.05 and 0.80 (got {new_fraction})")
            return False
        
        old_fraction = self.steps[step_name]
        self.steps[step_name] = new_fraction
        
        print(f"✓ Updated {step_name}:")
        print(f"  {old_fraction*100:.1f}% → {new_fraction*100:.1f}%")
        print(f"  {old_fraction*16:.2f} GB → {new_fraction*16:.2f} GB")
        
        return True
    
    def save_config(self):
        """Save updated configuration to file"""
        # Read current file
        content = self.config_file.read_text(encoding='utf-8')
        
        # Build new GPU_CONFIGS dict
        new_config_lines = ["    GPU_CONFIGS = {"]
        for step, fraction in sorted(self.steps.items()):
            comment = ""
            if fraction <= 0.15:
                comment = "  # Lightweight"
            elif fraction >= 0.30:
                comment = "  # Heavy"
            new_config_lines.append(f'        "{step}": {fraction:.2f},{comment}')
        new_config_lines.append("    }")
        new_config_block = "\n".join(new_config_lines)
        
        # Replace GPU_CONFIGS section
        import re
        pattern = r'GPU_CONFIGS = \{[^}]*\}'
        new_content = re.sub(pattern, new_config_block.strip(), content, flags=re.DOTALL)
        
        # Backup original
        backup_file = self.config_file.with_suffix('.py.bak')
        self.config_file.write_text(content, encoding='utf-8')  # Backup current
        backup_file.write_text(content, encoding='utf-8')
        
        # Write new config
        self.config_file.write_text(new_content, encoding='utf-8')
        
        print(f"\n✓ Configuration saved to: {self.config_file}")
        print(f"✓ Backup saved to: {backup_file}")
    
    def interactive_mode(self):
        """Interactive configuration mode"""
        print("\n" + "╔"+"═"*78+"╗")
        print("║" + " GPU Configuration Tuner ".center(78) + "║")
        print("╚"+"═"*78+"╝")
        
        while True:
            self.show_current_config()
            
            print("Commands:")
            print("  list           - Show current config")
            print("  set <step> <percent> - Set allocation (e.g., set audio_diarize 40)")
            print("  save           - Save changes")
            print("  reset          - Reset to defaults")
            print("  exit           - Exit without saving")
            print()
            
            try:
                cmd = input("Command: ").strip().lower()
                
                if cmd == "list":
                    continue
                elif cmd == "save":
                    self.save_config()
                    print("\n✓ Changes saved! Restart pipeline for changes to take effect.")
                    break
                elif cmd == "reset":
                    self.__init__()
                    print("\n✓ Reset to defaults")
                elif cmd == "exit":
                    print("\n👋 Exiting without saving")
                    break
                elif cmd.startswith("set "):
                    parts = cmd.split()
                    if len(parts) != 3:
                        print("❌ Usage: set <step_name> <percent>")
                        continue
                    
                    step_name = parts[1]
                    try:
                        percent = float(parts[2])
                        fraction = percent / 100.0
                        self.adjust_step(step_name, fraction)
                    except ValueError:
                        print(f"❌ Invalid percentage: {parts[2]}")
                else:
                    print(f"❌ Unknown command: {cmd}")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted")
                break
            except EOFError:
                break
    
    def apply_recommendations(self, report_file):
        """Apply recommendations from optimization report"""
        if not Path(report_file).exists():
            print(f"❌ Report file not found: {report_file}")
            return
        
        with open(report_file) as f:
            report = json.load(f)
        
        print("\n" + "="*80)
        print("Applying Optimization Recommendations")
        print("="*80)
        
        if 'step_analyses' in report:
            for step, analysis in report['step_analyses'].items():
                peak_percent = analysis['memory']['peak_percent']
                recommended = peak_percent / 100 * 1.2  # 120% of peak
                recommended = max(0.10, min(0.50, recommended))  # Clamp
                
                current = self.steps.get(step)
                if current and abs(recommended - current) > 0.02:  # >2% difference
                    print(f"\n{step}:")
                    print(f"  Current:     {current*100:.1f}%")
                    print(f"  Peak usage:  {peak_percent:.1f}%")
                    print(f"  Recommended: {recommended*100:.1f}%")
                    
                    response = input("  Apply? (y/n): ").strip().lower()
                    if response == 'y':
                        self.adjust_step(step, recommended)
        
        print("\n" + "="*80)
        save = input("\nSave all changes? (y/n): ").strip().lower()
        if save == 'y':
            self.save_config()


if __name__ == "__main__":
    import sys
    
    tuner = GPUConfigTuner()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "show":
            tuner.show_current_config()
        elif sys.argv[1] == "apply" and len(sys.argv) > 2:
            tuner.apply_recommendations(sys.argv[2])
        elif sys.argv[1] == "interactive":
            tuner.interactive_mode()
        else:
            print("Usage:")
            print("  python gpu_config_tuner.py show                    - Show current config")
            print("  python gpu_config_tuner.py interactive             - Interactive mode")
            print("  python gpu_config_tuner.py apply <report.json>     - Apply recommendations")
    else:
        # Default: interactive
        tuner.interactive_mode()
