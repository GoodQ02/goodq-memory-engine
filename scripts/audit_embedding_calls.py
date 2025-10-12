#!/usr/bin/env python3
"""
Mission: Audit Embedding Call Sites
Objective: Find all upsert_embedding calls missing scene_id parameter
Agent: Q
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple

def analyze_file(file_path: Path) -> List[Dict]:
    """Analyze a Python file for upsert_embedding calls"""
    issues = []
    
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        # Find upsert_embedding calls
        for i, line in enumerate(lines, 1):
            if 'upsert_embedding' in line and not line.strip().startswith('#'):
                # Check if it's a call (not a definition or import)
                if 'def upsert_embedding' not in line and 'from' not in line:
                    # Count parameters
                    # Look for the full call which might span multiple lines
                    call_start = i - 1
                    call_lines = [line]
                    
                    # Check if call continues on next lines
                    paren_count = line.count('(') - line.count(')')
                    j = i
                    while paren_count > 0 and j < len(lines):
                        call_lines.append(lines[j])
                        paren_count += lines[j].count('(') - lines[j].count(')')
                        j += 1
                    
                    full_call = ' '.join(call_lines)
                    
                    # Extract parameters
                    match = re.search(r'upsert_embedding\s*\((.*?)\)', full_call, re.DOTALL)
                    if match:
                        params = match.group(1)
                        # Count comma-separated parameters (rough estimate)
                        param_count = len([p for p in params.split(',') if p.strip()])
                        
                        # Check for scene_id keyword argument
                        has_scene_id = 'scene_id' in params
                        
                        issue = {
                            'file': str(file_path),
                            'line': i,
                            'code': line.strip(),
                            'param_count': param_count,
                            'has_scene_id': has_scene_id,
                            'full_call': full_call.strip()[:200]  # First 200 chars
                        }
                        
                        # Flag if suspicious (5 params without scene_id keyword)
                        if param_count == 5 and not has_scene_id:
                            issue['status'] = 'MISSING_SCENE_ID'
                        elif param_count < 5:
                            issue['status'] = 'TOO_FEW_PARAMS'
                        elif has_scene_id:
                            issue['status'] = 'OK'
                        else:
                            issue['status'] = 'CHECK_REQUIRED'
                        
                        issues.append(issue)
    
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
    
    return issues

def main():
    print("="*70)
    print("MISSION BRIEFING: Embedding Call Site Audit")
    print("="*70)
    print()
    
    # Find all step files
    steps_dir = Path("L:/goodq4all/steps")
    step_files = list(steps_dir.rglob("step.py"))
    
    print(f"🔍 Scanning {len(step_files)} step files...")
    print()
    
    all_issues = []
    files_with_issues = []
    
    for step_file in sorted(step_files):
        issues = analyze_file(step_file)
        if issues:
            all_issues.extend(issues)
            files_with_issues.append(step_file)
    
    # Report findings
    if not all_issues:
        print("✓ No upsert_embedding calls found")
        return 0
    
    print(f"📊 Found {len(all_issues)} upsert_embedding call(s) in {len(files_with_issues)} file(s)")
    print()
    
    # Group by status
    by_status = {}
    for issue in all_issues:
        status = issue['status']
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(issue)
    
    # Report critical issues first
    if 'MISSING_SCENE_ID' in by_status:
        print("🚨 CRITICAL: Missing scene_id Parameter")
        print("="*70)
        for issue in by_status['MISSING_SCENE_ID']:
            rel_path = Path(issue['file']).relative_to(Path("L:/goodq4all"))
            print(f"\n❌ {rel_path}:{issue['line']}")
            print(f"   {issue['code']}")
            print(f"   Parameters: {issue['param_count']}")
        print()
    
    # Report other statuses
    for status in ['TOO_FEW_PARAMS', 'CHECK_REQUIRED']:
        if status in by_status:
            print(f"⚠️  {status.replace('_', ' ')}")
            print("="*70)
            for issue in by_status[status]:
                rel_path = Path(issue['file']).relative_to(Path("L:/goodq4all"))
                print(f"\n⚠️  {rel_path}:{issue['line']}")
                print(f"   {issue['code']}")
                print(f"   Parameters: {issue['param_count']}")
            print()
    
    # Report OK calls
    if 'OK' in by_status:
        print(f"✓ {len(by_status['OK'])} call(s) correctly include scene_id")
        for issue in by_status['OK']:
            rel_path = Path(issue['file']).relative_to(Path("L:/goodq4all"))
            print(f"   ✓ {rel_path}:{issue['line']}")
        print()
    
    # Summary and recommendations
    print("="*70)
    print("MISSION SUMMARY")
    print("="*70)
    
    critical_count = len(by_status.get('MISSING_SCENE_ID', []))
    warning_count = len(by_status.get('TOO_FEW_PARAMS', [])) + len(by_status.get('CHECK_REQUIRED', []))
    ok_count = len(by_status.get('OK', []))
    
    print(f"Critical Issues:  {critical_count}")
    print(f"Warnings:         {warning_count}")
    print(f"Correct Calls:    {ok_count}")
    print()
    
    if critical_count > 0:
        print("⚠️  RECOMMENDATION: Fix critical issues before processing more data")
        print()
        print("Suggested Fix Pattern:")
        print("```python")
        print("# Add scene_id extraction")
        print("scene_id = item.get('scene_id') or item.get('id')")
        print("")
        print("# Add scene_id parameter to upsert_embedding call")
        print("upsert_embedding(cfg, hash_hex, faiss_id, source_path, modality,")
        print("                 scene_id=scene_id)  # <-- Add this")
        print("```")
        return 1
    else:
        print("✓ All embedding calls appear correct")
        return 0

if __name__ == '__main__':
    exit(main())
