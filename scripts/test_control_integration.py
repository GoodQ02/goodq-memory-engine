"""
Test Control Agent integration with ingestion pipeline
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all imports work"""
    print("Testing imports...")
    
    try:
        from agents.control_agent import ControlAgent
        print("[SYMBOL] ControlAgent imported")
    except Exception as e:
        print(f"[SYMBOL] ControlAgent import failed: {e}")
        return False
    
    try:
        from lib.llm_client import LLMClient
        print("[SYMBOL] LLMClient imported")
    except Exception as e:
        print(f"[SYMBOL] LLMClient import failed: {e}")
        return False
    
    return True

def test_control_agent_init():
    """Test Control Agent initialization"""
    print("\nTesting Control Agent initialization...")
    
    try:
        from agents.control_agent import ControlAgent
        agent = ControlAgent()
        print(f"[SYMBOL] Control Agent initialized successfully")
        print(f"  - LLM Client: {agent.llm is not None}")
        print(f"  - Config Healer: {agent.config_healer is not None}")
        print(f"  - Memory DB: {agent.memory_db_path.exists()}")
        return True
    except Exception as e:
        print(f"[SYMBOL] Control Agent init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_health():
    """Test LLM health checks"""
    print("\nTesting LLM health checks...")
    
    try:
        from lib.llm_client import LLMClient
        client = LLMClient()
        
        healthy_models = [m for m in client.models if client.health_status.get(m, {}).get('healthy', False)]
        print(f"[SYMBOL] LLM Client initialized")
        print(f"  - Total models: {len(client.models)}")
        print(f"  - Healthy models: {len(healthy_models)}")
        
        if healthy_models:
            print(f"  - Primary model: {healthy_models[0]}")
            return True
        else:
            print(f"  [SYMBOL] No healthy models found - orchestrator will run without LLM")
            return True  # Still OK, agent can work without LLM
            
    except Exception as e:
        print(f"[SYMBOL] LLM health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 70)
    print("Control Agent Integration Test")
    print("=" * 70)
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: Control Agent Init
    results.append(("Control Agent Init", test_control_agent_init()))
    
    # Test 3: LLM Health
    results.append(("LLM Health", test_llm_health()))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for name, passed in results:
        status = "[SYMBOL] PASS" if passed else "[SYMBOL] FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n[SYMBOL] All tests passed! Control Agent integration is ready.")
        return 0
    else:
        print("\n[SYMBOL] Some tests failed. Check errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
