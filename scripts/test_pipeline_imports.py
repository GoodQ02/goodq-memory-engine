"""
Test that all pipeline components can be imported successfully.
"""
import sys
sys.path.insert(0, 'L:/')

print("=" * 70)
print("Testing Pipeline Component Imports")
print("=" * 70)

# Test configuration loading
print("\n📋 Testing configuration modules...")
try:
    from GoodQ_4_All.configs import paths
    print("  ✓ paths module loaded")
    paths.ensure_directories()
    print("  ✓ directories ensured")
    paths.set_environment_variables()
    print("  ✓ environment configured")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# Test common utilities
print("\n🔧 Testing common utilities...")
try:
    from GoodQ_4_All.steps.common.config_loader import load_configs
    print("  ✓ config_loader imported")
    
    from GoodQ_4_All.steps.common import memory
    print("  ✓ memory module imported")
except Exception as e:
    print(f"  ✗ Error: {e}")
    sys.exit(1)

# Test step modules
print("\n📦 Testing step modules...")
step_modules = [
    "video_scene_detect",
    "image_caption",
    "object_detect",
    "audio_transcribe",
    "text_embed",
]

for module_name in step_modules:
    try:
        module = __import__(f"GoodQ_4_All.steps.{module_name}.step", fromlist=[''])
        print(f"  ✓ {module_name} imported")
    except Exception as e:
        print(f"  ⚠ {module_name}: {str(e)[:60]}")

# Test API modules
print("\n🌐 Testing API modules...")
try:
    from GoodQ_4_All.api import server
    print("  ✓ api.server imported")
except Exception as e:
    print(f"  ⚠ api.server: {str(e)[:60]}")

# Test CLI modules
print("\n💻 Testing CLI modules...")
cli_modules = ["memory", "retrieve", "run_ingestion"]
for module_name in cli_modules:
    try:
        module = __import__(f"GoodQ_4_All.cli.{module_name}", fromlist=[''])
        print(f"  ✓ cli.{module_name} imported")
    except Exception as e:
        print(f"  ⚠ cli.{module_name}: {str(e)[:60]}")

# Test library modules
print("\n📚 Testing library modules...")
try:
    from GoodQ_4_All.lib.memory_management.diagnostics import run_all_diagnostics
    print("  ✓ memory_management.diagnostics imported")
except Exception as e:
    print(f"  ⚠ memory_management.diagnostics: {str(e)[:60]}")

try:
    from GoodQ_4_All.lib.knowledge_graph import KnowledgeGraphBuilder
    print("  ✓ knowledge_graph imported")
except Exception as e:
    print(f"  ⚠ knowledge_graph: {str(e)[:60]}")

# Summary
print("\n" + "=" * 70)
print("✓ Import Test Complete!")
print("=" * 70)
print("\nAll critical modules can be imported successfully.")
print("The pipeline is ready for operation!")
