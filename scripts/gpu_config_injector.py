"""
Inject GPU Configuration into Pipeline Steps
Adds GPU config imports to all GPU-utilizing steps
"""

import os
import re
from pathlib import Path

class GPUConfigInjector:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent.parent
        self.steps_dir = self.base_dir / "steps"
        
        # Steps that use GPU (PyTorch/CUDA)
        self.gpu_steps = [
            "audio_diarize",
            "audio_transcribe",
            "audio_embed_clap",
            "audio_emotion",
            "face_embed",
            "emotion_classify",
            "text_embed",
            "image_embed_clip",
            "image_embed_dino",
            "object_detect",
            "object_track_yolo",
            "image_caption",
            "image_ocr",
            "llm_chat",
        ]
        
        self.import_statement = """# GPU Configuration - Auto-configured on import
from steps.common.gpu_config import configure_gpu, get_device, clear_cache, print_memory_stats

"""
    
    def check_has_gpu_import(self, filepath):
        """Check if file already has GPU config import"""
        content = filepath.read_text(encoding='utf-8')
        return 'gpu_config' in content or 'from steps.common.gpu_config import' in content
    
    def inject_import(self, filepath):
        """Inject GPU config import at the top of the file"""
        content = filepath.read_text(encoding='utf-8')
        
        # Find the right place to inject (after future imports, before other imports)
        lines = content.split('\n')
        inject_at = 0
        
        # Skip shebang and encoding declarations
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('#') or stripped.startswith('"""') or not stripped:
                inject_at = i + 1
                continue
            elif stripped.startswith('from __future__'):
                inject_at = i + 1
                continue
            else:
                break
        
        # Check if already imported
        if any('gpu_config' in line for line in lines):
            return False, "Already has GPU config import"
        
        # Inject the import
        lines.insert(inject_at, self.import_statement)
        
        new_content = '\n'.join(lines)
        filepath.write_text(new_content, encoding='utf-8')
        
        return True, f"Injected at line {inject_at + 1}"
    
    def add_device_config_call(self, filepath, step_name):
        """Add explicit configure_gpu() call if needed"""
        content = filepath.read_text(encoding='utf-8')
        
        # Check if main function exists
        patterns = [
            rf"def {step_name}\(",
            r"def run\(",
            r"def process\(",
            r"def main\(",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                # Check if configure_gpu is already called
                if 'configure_gpu(' in content:
                    return False, "Already calls configure_gpu"
                
                # Find the function and add call at start
                func_start = match.end()
                # Find end of docstring if exists
                after_func = content[func_start:]
                
                # Look for first non-docstring, non-comment line
                lines = after_func.split('\n')
                insert_at = 0
                in_docstring = False
                
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    if '"""' in stripped or "'''" in stripped:
                        if not in_docstring:
                            in_docstring = True
                        else:
                            in_docstring = False
                            insert_at = i + 1
                            break
                    elif not in_docstring and stripped and not stripped.startswith('#'):
                        insert_at = i
                        break
                
                # Get indentation from next line
                next_line = lines[insert_at] if insert_at < len(lines) else "    "
                indent = len(next_line) - len(next_line.lstrip())
                indent_str = ' ' * indent
                
                gpu_call = f'\n{indent_str}# Configure GPU for this step\n{indent_str}gpu_info = configure_gpu("{step_name}")\n{indent_str}device = get_device()\n'
                
                # Insert the call
                lines.insert(insert_at, gpu_call)
                new_after_func = '\n'.join(lines)
                new_content = content[:func_start] + new_after_func
                
                filepath.write_text(new_content, encoding='utf-8')
                return True, f"Added configure_gpu call in main function"
        
        return False, "No main function found"
    
    def inject_all_steps(self, dry_run=False):
        """Inject GPU config into all GPU-using steps"""
        print("=" * 80)
        print("GPU Configuration Injector")
        print("=" * 80)
        print(f"Base directory: {self.base_dir}")
        print(f"Steps directory: {self.steps_dir}")
        print(f"Target steps: {len(self.gpu_steps)}")
        if dry_run:
            print("\n⚠ DRY RUN MODE - No files will be modified")
        print("=" * 80)
        print()
        
        results = {
            "success": [],
            "skipped": [],
            "failed": []
        }
        
        for step_name in self.gpu_steps:
            step_dir = self.steps_dir / step_name
            step_file = step_dir / "step.py"
            
            if not step_file.exists():
                print(f"⚠ {step_name:25s} - step.py not found")
                results["skipped"].append(step_name)
                continue
            
            print(f"📁 {step_name:25s}", end=" - ")
            
            try:
                # Check if already has import
                if self.check_has_gpu_import(step_file):
                    print("✓ Already configured")
                    results["skipped"].append(step_name)
                    continue
                
                if not dry_run:
                    # Inject import
                    success, msg = self.inject_import(step_file)
                    if success:
                        print(f"✅ {msg}")
                        results["success"].append(step_name)
                    else:
                        print(f"⏭ {msg}")
                        results["skipped"].append(step_name)
                else:
                    print("Would inject import")
                    results["success"].append(step_name)
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                results["failed"].append(step_name)
        
        # Print summary
        print()
        print("=" * 80)
        print("Summary")
        print("=" * 80)
        print(f"✅ Success: {len(results['success'])}")
        print(f"⏭ Skipped: {len(results['skipped'])}")
        print(f"❌ Failed: {len(results['failed'])}")
        
        if results["success"]:
            print(f"\nSuccessfully injected:")
            for step in results["success"]:
                print(f"  • {step}")
        
        if results["failed"]:
            print(f"\n❌ Failed:")
            for step in results["failed"]:
                print(f"  • {step}")
        
        print("=" * 80)
        
        return results
    
    def verify_all_configs(self):
        """Verify GPU config is properly imported in all GPU steps"""
        print("=" * 80)
        print("Verifying GPU Configuration")
        print("=" * 80)
        print()
        
        results = {
            "configured": [],
            "missing": [],
            "not_found": []
        }
        
        for step_name in self.gpu_steps:
            step_dir = self.steps_dir / step_name
            step_file = step_dir / "step.py"
            
            if not step_file.exists():
                print(f"⚠ {step_name:25s} - step.py not found")
                results["not_found"].append(step_name)
                continue
            
            if self.check_has_gpu_import(step_file):
                print(f"✅ {step_name:25s} - GPU config present")
                results["configured"].append(step_name)
            else:
                print(f"❌ {step_name:25s} - GPU config MISSING")
                results["missing"].append(step_name)
        
        print()
        print("=" * 80)
        print("Verification Summary")
        print("=" * 80)
        print(f"✅ Configured: {len(results['configured'])}/{len(self.gpu_steps)}")
        print(f"❌ Missing: {len(results['missing'])}")
        print(f"⚠ Not found: {len(results['not_found'])}")
        print("=" * 80)
        
        return results


if __name__ == "__main__":
    import sys
    
    injector = GPUConfigInjector()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "inject":
            dry_run = "--dry-run" in sys.argv
            injector.inject_all_steps(dry_run=dry_run)
        elif command == "verify":
            injector.verify_all_configs()
        else:
            print(f"Unknown command: {command}")
            print("Usage:")
            print("  python gpu_config_injector.py inject [--dry-run]")
            print("  python gpu_config_injector.py verify")
    else:
        # Default: verify
        injector.verify_all_configs()
