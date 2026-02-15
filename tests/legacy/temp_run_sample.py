#!/usr/bin/env python
"""
Temporary wrapper to run ingestion on sample.mp4 with proper imports
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now run the ingestion CLI
from cli.run_ingestion import APP

if __name__ == '__main__':
    # Run with arguments
    sys.argv = [
        'run_ingestion.py',
        '--input-dir', 'samples/ingestion',
        '--workspace', 'logs/test_workspace',
        '--output', 'logs/test_results.json',
        '--verbose',
        '--force'
    ]
    
    APP()
