"""
CRITICAL EMOJI PURGE - Remove ALL emojis from Python files
This fixes Windows 'charmap' codec errors that cause ingestion to crash
"""
import re
from pathlib import Path

# Emoji to text replacements
EMOJI_MAP = {
    '[CONFIG]': '[CONFIG]',
    '[LOG]': '[LOG]',
    '[VIDEO]': '[VIDEO]',
    '[NOTE]': '[NOTE]',
    '[TIP]': '[TIP]',
    '[WARN]': '[WARN]',
    '[OK]': '[OK]',
    '[FAIL]': '[FAIL]',
    '[PASS]': '[PASS]',
    '[INFO]': '[INFO]',
    '[ERROR]': '[ERROR]',
    '[TIMER]': '[TIMER]',
    '[BOT]': '[BOT]',
    '[SEARCH]': '[SEARCH]',
    '[DIR]': '[DIR]',
    '[SCENE]': '[SCENE]',
    '[TARGET]': '[TARGET]',
    '[LAUNCH]': '[LAUNCH]',
    '[FAST]': '[FAST]',
    '[SYNC]': '[SYNC]',
    '[SAVE]': '[SAVE]',
    '[STATS]': '[STATS]',
    '[UI]': '[UI]',
    '[AI]': '[AI]',
    '[AUDIO]': '[AUDIO]',
    '[IMAGE]': '[IMAGE]',
}

# Regex to match ALL emoji ranges
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002600-\U000027BF"  # misc symbols
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
    "]+", 
    flags=re.UNICODE
)

def remove_emojis_from_file(file_path: Path) -> bool:
    """Remove ALL emojis from a Python file"""
    try:
        # Read with UTF-8
        content = file_path.read_text(encoding='utf-8')
        original = content
        
        # Replace known emojis first
        for emoji, replacement in EMOJI_MAP.items():
            content = content.replace(emoji, replacement)
        
        # Remove any remaining emojis
        content = EMOJI_PATTERN.sub('[SYMBOL]', content)
        
        if content != original:
            # Write back with UTF-8
            file_path.write_text(content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"[FAIL] {file_path}: {e}")
        return False

def main():
    root = Path("L:/goodq4all")
    
    # Target files
    py_files = list(root.glob("**/*.py"))
    
    fixed_count = 0
    total_count = len(py_files)
    
    print(f"[INFO] Scanning {total_count} Python files...")
    
    for py_file in py_files:
        # Skip vendor directory
        if "vendor" in py_file.parts:
            continue
            
        if remove_emojis_from_file(py_file):
            print(f"[OK] Fixed: {py_file.relative_to(root)}")
            fixed_count += 1
    
    print(f"\n[COMPLETE] Fixed {fixed_count}/{total_count} files")

if __name__ == "__main__":
    main()
