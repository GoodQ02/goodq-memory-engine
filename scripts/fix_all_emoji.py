"""
Fix All Emoji Characters - Production Quality Script
Removes all emoji/unicode characters that cause Windows charmap encoding errors
"""

import re
from pathlib import Path

# Emoji to ASCII mapping
EMOJI_MAP = {
    '🔧': '[CONFIG]',
    '🧠': '[AI]',
    '✓': '[OK]',
    '✅': '[PASS]',
    '✗': '[FAIL]',
    '❌': '[FAIL]',
    '⚠️': '[WARN]',
    '⏳': '[WAIT]',
    '📹': '[VIDEO]',
    '📁': '[DIR]',
    '🔍': '[SEARCH]',
    '🟩': '===',
    '🟦': '===',
    '🟥': '===',
    '🤖': '[BOT]',
    '⭐': '*',
    '🎯': '[TARGET]',
}

# Files to fix (Python files only, skip vendor)
FILES_TO_FIX = [
    'lib/control_agent.py',
    'lib/config_healer.py',
    'lib/llm_client.py',
    'cli/watchdog.py',
    'cli/run_ingestion.py',
    'cli/system_status.py',
    'cli/monitor_ingestion.py',
    'cli/test_ingestion.py',
    'pipelines/direct_ingestion.py',
    'agents/control_agent.py',
    'agents/config_healer.py',
]

def fix_emoji_in_file(filepath: Path) -> bool:
    """Remove emoji from a single file"""
    if not filepath.exists():
        print(f"  [SKIP] {filepath} - not found")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace all known emoji
        for emoji, replacement in EMOJI_MAP.items():
            if emoji in content:
                content = content.replace(emoji, replacement)
                print(f"  [FIX] {filepath.name}: {emoji} -> {replacement}")
        
        # Remove any remaining emoji (Unicode range)
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F700-\U0001F77F"  # alchemical symbols
            u"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            u"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            u"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            u"\U0001FA00-\U0001FA6F"  # Chess Symbols
            u"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            u"\U00002702-\U000027B0"  # Dingbats
            "]+", flags=re.UNICODE)
        
        content = emoji_pattern.sub('[SYMBOL]', content)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        
        return False
        
    except Exception as e:
        print(f"  [ERROR] {filepath}: {e}")
        return False

def main():
    print("="*80)
    print("  EMOJI REMOVAL - PRODUCTION FIX")
    print("="*80)
    
    repo_root = Path("L:/goodq4all")
    fixed_count = 0
    
    for file_path in FILES_TO_FIX:
        full_path = repo_root / file_path
        if fix_emoji_in_file(full_path):
            fixed_count += 1
    
    print(f"\n[COMPLETE] Fixed {fixed_count} files")
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
