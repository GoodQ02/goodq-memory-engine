#!/usr/bin/env python3
"""
GoodQ UI Configuration Validator
Checks all HTML/JS/BAT files for port consistency
"""
import re
from pathlib import Path
from collections import defaultdict

def validate_ui_config():
    """Validate all UI configuration files for consistency"""
    
    base_dir = Path("L:/goodq4all")
    
    # Expected configuration
    EXPECTED_PORT = "30000"
    EXPECTED_API_BASE = f"http://localhost:{EXPECTED_PORT}/api"
    
    # Files to check
    files_to_check = {
        "index.html": ["HTML", "Frontend"],
        "dashboard.html": ["HTML", "Frontend"],
        "test_api.html": ["HTML", "Test"],
        "api_server.py": ["Python", "Backend"],
        "web_interface.py": ["Python", "Legacy Backend"],
        "serve_chat.py": ["Python", "Legacy Server"],
        "LAUNCH_GOODQ.bat": ["Batch", "Launcher"],
        "LAUNCH_WEB_INTERFACE.bat": ["Batch", "Launcher"],
        "START_FULL_SYSTEM_TEST.bat": ["Batch", "Launcher"],
    }
    
    results = {
        "correct": [],
        "incorrect": [],
        "warnings": [],
        "errors": []
    }
    
    port_pattern = re.compile(r'(?:localhost:|port\s*[=:]\s*)(\d{4,5})', re.IGNORECASE)
    
    print("=" * 80)
    print("GoodQ UI Configuration Validator")
    print("=" * 80)
    print(f"\n✓ Expected API Port: {EXPECTED_PORT}")
    print(f"✓ Expected API Base: {EXPECTED_API_BASE}\n")
    
    for filename, (file_type, category) in files_to_check.items():
        filepath = base_dir / filename
        
        # Skip legacy files
        if "LEGACY" in filename or not filepath.exists():
            if not filepath.exists() and "Legacy" not in category:
                results["warnings"].append(f"File not found: {filename}")
            continue
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find all port references
            ports_found = port_pattern.findall(content)
            
            if not ports_found:
                if file_type in ["Python", "Batch"] and "Legacy" not in category:
                    results["warnings"].append(f"{filename}: No port configuration found")
                continue
            
            # Check each port reference
            incorrect_ports = [p for p in ports_found if p != EXPECTED_PORT]
            
            if incorrect_ports:
                unique_ports = set(incorrect_ports)
                results["incorrect"].append({
                    "file": filename,
                    "type": file_type,
                    "category": category,
                    "wrong_ports": list(unique_ports),
                    "occurrences": len(incorrect_ports)
                })
            else:
                results["correct"].append({
                    "file": filename,
                    "type": file_type,
                    "port": EXPECTED_PORT,
                    "occurrences": len(ports_found)
                })
                
        except Exception as e:
            results["errors"].append(f"{filename}: {str(e)}")
    
    # Print results
    print("-" * 80)
    print("VALIDATION RESULTS")
    print("-" * 80)
    
    if results["correct"]:
        print(f"\n✅ CORRECT ({len(results['correct'])} files):")
        for item in results["correct"]:
            print(f"   ✓ {item['file']:<35} Port {item['port']} ({item['occurrences']} refs)")
    
    if results["incorrect"]:
        print(f"\n❌ INCORRECT ({len(results['incorrect'])} files):")
        for item in results["incorrect"]:
            ports_str = ", ".join(item['wrong_ports'])
            print(f"   ✗ {item['file']:<35} Wrong port(s): {ports_str} ({item['occurrences']} refs)")
    
    if results["warnings"]:
        print(f"\n⚠️  WARNINGS ({len(results['warnings'])}):")
        for warning in results["warnings"]:
            print(f"   ⚠  {warning}")
    
    if results["errors"]:
        print(f"\n🚨 ERRORS ({len(results['errors'])}):")
        for error in results["errors"]:
            print(f"   🚨 {error}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_checked = len(results["correct"]) + len(results["incorrect"])
    
    if len(results["incorrect"]) == 0 and len(results["errors"]) == 0:
        print("✅ ALL FILES VALIDATED SUCCESSFULLY!")
        print(f"   • {total_checked} files checked")
        print(f"   • All using port {EXPECTED_PORT}")
        print(f"   • Ready for production use")
        return True
    else:
        print("❌ VALIDATION FAILED")
        print(f"   • {len(results['correct'])} files correct")
        print(f"   • {len(results['incorrect'])} files need fixing")
        print(f"   • {len(results['errors'])} errors encountered")
        print(f"\n📝 Action Required: Fix the incorrect files listed above")
        return False

if __name__ == "__main__":
    success = validate_ui_config()
    exit(0 if success else 1)
