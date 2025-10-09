"""Test paths configuration after reorganization."""
import sys
sys.path.insert(0, 'L:/')

from GoodQ_4_All.configs.paths import *
import os

print("=" * 70)
print("Testing Paths Configuration")
print("=" * 70)

print("\n✓ Paths module imported successfully!")

print("\n📁 Creating directories...")
ensure_directories()
print("✓ All directories created!")

print("\n🔧 Setting environment variables...")
set_environment_variables()
print("✓ Environment configured!")

print("\n📊 Environment Variables:")
print(f"   HF_HOME: {os.environ.get('HF_HOME')}")
print(f"   TORCH_HOME: {os.environ.get('TORCH_HOME')}")
print(f"   TRANSFORMERS_CACHE: {os.environ.get('TRANSFORMERS_CACHE')}")
print(f"   PYTHONNOUSERSITE: {os.environ.get('PYTHONNOUSERSITE')}")

print("\n📁 Key Paths:")
print(f"   PROJECT_ROOT: {PROJECT_ROOT}")
print(f"   DATA_ROOT: {DATA_ROOT}")
print(f"   MEMORY_DB: {MEMORY_DB}")
print(f"   KNOWLEDGE_GRAPH_DB: {KNOWLEDGE_GRAPH_DB}")
print(f"   LOGS_DIR: {LOGS_DIR}")
print(f"   IMPORT_INBOX: {IMPORT_INBOX}")

print("\n✓ Configuration test complete!")
