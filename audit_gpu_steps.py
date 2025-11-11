import os
import ast
import json

results = {
    "gpu_steps": [],
    "cpu_steps": [],
    "needs_refactor": [],
    "already_using_gpumanager": []
}

def check_step_file(step_name, file_path):
    """Check if a step file uses GPU and how"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        uses_gpu = any(x in content for x in [
            'torch.cuda', 'tensorflow', 'device=', 'GPU', 'CUDA'
        ])
        
        uses_gpumanager = 'GPUManager' in content or 'setup_step_gpu' in content
        uses_manual_cuda = 'CUDA_VISIBLE_DEVICES' in content and not uses_gpumanager
        
        imports_torch = 'import torch' in content or 'from torch' in content
        
        info = {
            "step": step_name,
            "file": file_path,
            "uses_gpu": uses_gpu,
            "uses_gpumanager": uses_gpumanager,
            "uses_manual_cuda": uses_manual_cuda,
            "imports_torch": imports_torch
        }
        
        if uses_gpumanager:
            results["already_using_gpumanager"].append(info)
        elif uses_manual_cuda or (uses_gpu and imports_torch):
            results["needs_refactor"].append(info)
            results["gpu_steps"].append(step_name)
        elif uses_gpu:
            results["gpu_steps"].append(step_name)
        else:
            results["cpu_steps"].append(step_name)
        
        return info
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

# Scan all step directories
steps_dir = 'steps'
for item in os.listdir(steps_dir):
    item_path = os.path.join(steps_dir, item)
    if os.path.isdir(item_path):
        step_file = os.path.join(item_path, 'step.py')
        if os.path.exists(step_file):
            check_step_file(item, step_file)

# Print results
print("=" * 80)
print("GPU STEP AUDIT RESULTS")
print("=" * 80)

print(f"\n📊 Total GPU Steps: {len(set(results['gpu_steps']))}")
print(f"💻 Total CPU Steps: {len(results['cpu_steps'])}")
print(f"✅ Using GPUManager: {len(results['already_using_gpumanager'])}")
print(f"🔧 Needs Refactor: {len(results['needs_refactor'])}")

print("\n" + "=" * 80)
print("STEPS THAT NEED REFACTORING")
print("=" * 80)
for step in results["needs_refactor"]:
    status = []
    if step["uses_manual_cuda"]:
        status.append("manual CUDA")
    if step["imports_torch"]:
        status.append("uses torch")
    if step["uses_gpu"]:
        status.append("GPU detected")
    print(f"\n🔧 {step['step']}")
    print(f"   Status: {', '.join(status)}")
    print(f"   File: {step['file']}")

print("\n" + "=" * 80)
print("STEPS ALREADY USING GPUMANAGER")
print("=" * 80)
for step in results["already_using_gpumanager"]:
    print(f"✅ {step['step']}")

# Save to file
with open('GPU_AUDIT_RESULTS.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 80)
print("✅ Audit complete! Results saved to GPU_AUDIT_RESULTS.json")
print("=" * 80)
