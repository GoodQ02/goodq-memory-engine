"""
Phase 2: Comprehensive Endpoint Validation
Tests all UI-required endpoints for proper response structure
"""

import requests
import json
from typing import Dict, Any, List
from datetime import datetime

API_BASE = "http://localhost:30000/api"

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

class EndpointTester:
    def __init__(self):
        self.results = []
        
    def test(self, name: str, url: str, method: str = "GET", required_fields: List[str] = None, data: Dict = None):
        """Test an endpoint and validate response"""
        try:
            if method == "GET":
                resp = requests.get(url, timeout=5)
            elif method == "POST":
                resp = requests.post(url, json=data or {}, timeout=5)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            success = resp.status_code == 200
            response_data = resp.json() if success else None
            
            # Validate required fields
            missing_fields = []
            if success and required_fields and response_data:
                for field in required_fields:
                    if '.' in field:
                        # Nested field check
                        parts = field.split('.')
                        current = response_data
                        for part in parts:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                missing_fields.append(field)
                                break
                    else:
                        if field not in response_data:
                            missing_fields.append(field)
            
            result = {
                "name": name,
                "url": url,
                "method": method,
                "status_code": resp.status_code,
                "success": success and len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "response_sample": str(response_data)[:200] if response_data else None
            }
            
            self.results.append(result)
            
            status_icon = f"{GREEN}[SYMBOL]{RESET}" if result["success"] else f"{RED}[SYMBOL]{RESET}"
            print(f"{status_icon} {name:40} {resp.status_code}")
            if missing_fields:
                print(f"   {YELLOW}Missing fields: {', '.join(missing_fields)}{RESET}")
            
            return result
            
        except Exception as e:
            result = {
                "name": name,
                "url": url,
                "method": method,
                "success": False,
                "error": str(e)
            }
            self.results.append(result)
            print(f"{RED}[SYMBOL]{RESET} {name:40} ERROR: {str(e)[:50]}")
            return result
    
    def print_summary(self):
        """Print test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.get("success"))
        failed = total - passed
        
        print("\n" + "="*80)
        print(f"PHASE 2 VALIDATION SUMMARY")
        print("="*80)
        print(f"Total Endpoints: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        print("="*80)
        
        if failed > 0:
            print(f"\n{RED}Failed Endpoints:{RESET}")
            for result in self.results:
                if not result.get("success"):
                    print(f"  - {result['name']}")
                    if "error" in result:
                        print(f"    Error: {result['error']}")
                    if result.get("missing_fields"):
                        print(f"    Missing: {', '.join(result['missing_fields'])}")


def main():
    print("="*80)
    print("[SEARCH] GoodQ4All - Phase 2: Endpoint Validation")
    print("="*80)
    print()
    
    tester = EndpointTester()
    
    # Core Status Endpoints
    print("[STATS] Core Status Endpoints")
    print("-"*80)
    tester.test("Status", f"{API_BASE}/status", required_fields=["status", "version", "components", "gpu", "models"])
    tester.test("Progress", f"{API_BASE}/progress", required_fields=["status", "current_video"])
    tester.test("Queue", f"{API_BASE}/queue")
    tester.test("Recent Activity", f"{API_BASE}/recent-activity")
    print()
    
    # Engine & Process Endpoints
    print("[SYMBOL]️  Engine & Process Endpoints")
    print("-"*80)
    tester.test("Pipeline Engines", f"{API_BASE}/pipeline-engines")
    tester.test("Legacy Engines", f"{API_BASE}/engines")
    tester.test("Processes", f"{API_BASE}/processes", required_fields=["processes", "gpu_status"])
    tester.test("WSL2 Status", f"{API_BASE}/wsl2-status")
    tester.test("Command Center", f"{API_BASE}/command-center", required_fields=["status", "health", "logs"])
    print()
    
    # Data & Search Endpoints
    print("[DIR] Data & Search Endpoints")
    print("-"*80)
    tester.test("Scenes", f"{API_BASE}/scenes")
    tester.test("Entities", f"{API_BASE}/entities")
    tester.test("Knowledge Graph", f"{API_BASE}/knowledge_graph")
    print()
    
    # Analytics Endpoints
    print("[SYMBOL] Analytics Endpoints")
    print("-"*80)
    tester.test("Analytics: Knowledge Graph", f"{API_BASE}/analytics/knowledge-graph")
    tester.test("Analytics: Timeline", f"{API_BASE}/analytics/timeline")
    tester.test("Analytics: Emotions", f"{API_BASE}/analytics/emotions")
    tester.test("Analytics: Embeddings", f"{API_BASE}/analytics/embeddings")
    print()
    
    # Model & LLM Endpoints
    print("[BOT] Model & LLM Endpoints")
    print("-"*80)
    tester.test("Models", f"{API_BASE}/models")
    print()
    
    # Action Endpoints (POST)
    print("[SCENE] Action Endpoints")
    print("-"*80)
    tester.test("Test Audio", f"{API_BASE}/test-audio", method="POST", data={})
    tester.test("Control Agent Chat", f"{API_BASE}/chat/control-agent", method="POST", 
                data={"type": "user_query", "query": "test", "timestamp": datetime.now().isoformat()})
    print()
    
    # Print Summary
    tester.print_summary()
    
    # Save detailed results
    results_file = "L:/goodq4all/reports/endpoint_validation_phase2.json"
    import os
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(tester.results),
                "passed": sum(1 for r in tester.results if r.get("success")),
                "failed": sum(1 for r in tester.results if not r.get("success"))
            },
            "results": tester.results
        }, f, indent=2)
    
    print(f"\n[SYMBOL] Detailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
