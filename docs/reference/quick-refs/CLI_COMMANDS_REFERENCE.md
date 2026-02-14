# CLI Commands Reference

Complete reference for all GoodQ4All command-line tools.

---

## Overview

GoodQ4All provides several CLI tools for different operations:

- **Ingestion** - Video/media processing
- **Retrieval** - Search and query
- **Monitoring** - System status and health
- **Memory** - Database management
- **Knowledge Graph** - Entity and relationship queries

All commands should be run from the project root (`<project_root>\`) with the `goodq_zenml` conda environment activated:

```powershell
conda activate goodq_zenml
cd <project_root>
```

---

## Ingestion Commands

### `run_ingestion.py`
Process video/media files through the complete ingestion pipeline.

**Usage:**
```powershell
python cli\run_ingestion.py --video "path\to\video.mp4"
```

**Options:**
- `--video PATH` - Path to video file to process
- `--verbose` - Enable verbose output for debugging
- `--skip-steps STEPS` - Skip specific pipeline steps (comma-separated)

**Examples:**
```powershell
# Basic processing
python cli\run_ingestion.py --video "C:\Videos\birthday.mp4"

# With verbose output
python cli\run_ingestion.py --video "C:\Videos\birthday.mp4" --verbose

# Skip specific steps
python cli\run_ingestion.py --video "C:\Videos\birthday.mp4" --skip-steps "audio_analysis"
```

### `list_inbox.py`
List files in the import inbox awaiting processing.

**Usage:**
```powershell
python cli\list_inbox.py
```

**Output:**
- Lists all files in `<project_root>\import_inbox\`
- Shows file sizes and types
- Identifies supported formats

### `monitor_ingestion.py`
Monitor active ingestion progress in real-time.

**Usage:**
```powershell
python cli\monitor_ingestion.py
```

**Features:**
- Shows current processing status
- Displays pipeline progress
- Updates in real-time
- Shows estimated completion times

---

## Retrieval & Search Commands

### `retrieve.py`
Semantic search across processed content using vector embeddings.

**Usage:**
```powershell
python cli\retrieve.py --query "search text" --top N
```

**Options:**
- `--query TEXT` - Search query (required)
- `--top N` - Number of results to return (default: 5)
- `--threshold FLOAT` - Minimum similarity score (0.0-1.0)
- `--json` - Output results in JSON format

**Examples:**
```powershell
# Basic search
python cli\retrieve.py --query "kids playing at beach"

# Get top 10 results
python cli\retrieve.py --query "sunset" --top 10

# Filter by similarity threshold
python cli\retrieve.py --query "birthday party" --threshold 0.8

# JSON output
python cli\retrieve.py --query "dogs" --json
```

### `nl_query.py`
Natural language interface for knowledge graph queries.

**Usage:**
```powershell
python cli\nl_query.py
```

**Features:**
- Interactive natural language query interface
- Powered by LLM for understanding complex questions
- Queries the knowledge graph intelligently
- Provides contextual answers with citations

**Examples:**
```powershell
# Start interactive query session
python cli\nl_query.py

# Example queries:
"Show me all scenes with people wearing blue"
"Find videos from birthday parties"
"What events happened between 2:00 and 5:00?"
```

### `graph_query.py`
Direct knowledge graph query CLI with structured commands.

**Usage:**
```powershell
python cli\graph_query.py [COMMAND] [OPTIONS]
```

**Commands:**

#### `stats`
Show knowledge graph statistics.
```powershell
python cli\graph_query.py stats
```

#### `find-person`
Find scenes containing a specific person.
```powershell
python cli\graph_query.py find-person "John"
```

#### `scene-context`
Get detailed context for a specific scene.
```powershell
python cli\graph_query.py scene-context scene_0042
python cli\graph_query.py scene-context scene_0042 --json
```

#### `list-entities`
List all entities in the graph.
```powershell
python cli\graph_query.py list-entities
python cli\graph_query.py list-entities --type person --limit 20
```

#### `search`
Search scenes by objects, emotions, or other attributes.
```powershell
python cli\graph_query.py search --objects person car --emotions happy
python cli\graph_query.py search --start-time 0 --end-time 100 --min-confidence 0.8
```

#### `story`
Generate narrative story from time range.
```powershell
python cli\graph_query.py story 0 60
python cli\graph_query.py story 0 60 --json
```

#### `track-concept`
Track a concept across scenes.
```powershell
python cli\graph_query.py track-concept "birthday"
```

#### `related-scenes`
Find scenes related to a specific scene.
```powershell
python cli\graph_query.py related-scenes scene_0042 --max-results 10
```

#### `export`
Export scenes to JSON.
```powershell
python cli\graph_query.py export 1 2 3 4 output.json
```

**Global Options:**
- `--graph-db PATH` - Path to knowledge graph database (default: `<GOODQ_DATA_ROOT>/GoodQ_Data/knowledge_graph.db`)

---

## Memory & Database Commands

### `memory.py`
Memory management and diagnostic CLI.

**Usage:**
```powershell
python cli\memory.py [COMMAND] [OPTIONS]
```

**Commands:**

#### `health-check`
Run comprehensive memory system diagnostics.
```powershell
python cli\memory.py health-check
python cli\memory.py health-check --output-file report.json
```

**Returns:**
- Database connectivity status
- Schema validation
- Data integrity checks
- Performance metrics
- Warnings and errors

#### `backup`
Create backup of memory databases.
```powershell
python cli\memory.py backup
```

**Output:**
- Creates timestamped backup in logs directory
- Returns path to backup directory

#### `verify-schema`
Verify database schema integrity.
```powershell
python cli\memory.py verify-schema
```

**Checks:**
- Schema matches expected structure
- All required tables exist
- Indexes are properly configured
- No schema drift detected

---

## System Monitoring Commands

### `system_status.py`
Complete system health and diagnostic dashboard.

**Usage:**
```powershell
python cli\system_status.py
```

**Displays:**
- **Environment Status**
  - Python version
  - Repository root
  - Critical dependencies
- **Configuration Status**
  - Config file validation
  - Path verification
  - Model availability
- **Database Status**
  - Connection health
  - Record counts
  - Storage usage
- **Processing Status**
  - Active jobs
  - Recent completions
  - Error summary
- **Model Status**
  - GPU availability
  - Model loading status
  - VRAM usage

### `print_config.py`
Display current configuration.

**Usage:**
```powershell
python cli\print_config.py
```

**Output:**
- Complete configuration tree
- Resolved paths
- Active settings
- Environment variables

---

## Processing Utilities

### `step_runner.py`
Run individual pipeline steps in isolation (advanced).

**Usage:**
```powershell
python cli\step_runner.py --step STEP_NAME --input INPUT_JSON
```

**Options:**
- `--step STEP_NAME` - Name of step to run
- `--input PATH` - JSON file with input data
- `--output PATH` - Where to write results
- `--config PATH` - Custom config file

**Examples:**
```powershell
# Run audio transcription step only
python cli\step_runner.py --step audio_transcription --input scene_data.json

# Run object detection with custom config
python cli\step_runner.py --step object_detection --input scene.json --config custom.yaml
```

### `test_ingestion.py`
Test ingestion pipeline with diagnostic output.

**Usage:**
```powershell
python cli\test_ingestion.py --video "path\to\test_video.mp4"
```

**Features:**
- Detailed step-by-step logging
- Timing information for each step
- Error diagnostics
- Validates pipeline without full processing

---

## Chroma Vector Store Commands

### `chroma_store.py`
Direct ChromaDB operations (low-level).

**Usage:**
```powershell
python cli\chroma_store.py [COMMAND]
```

**Commands:**
- `list-collections` - List all vector collections
- `stats` - Show storage statistics
- `query` - Direct vector query
- `clear` - Clear specific collection (destructive)

---

## Common Patterns

### Sequential Processing
```powershell
# 1. Check inbox
python cli\list_inbox.py

# 2. Process a file
python cli\run_ingestion.py --video "inbox\video.mp4"

# 3. Monitor progress
python cli\monitor_ingestion.py

# 4. Verify in database
python cli\memory.py health-check

# 5. Search content
python cli\retrieve.py --query "my search"
```

### Debugging Workflow
```powershell
# Check system health
python cli\system_status.py

# Verify configuration
python cli\print_config.py

# Check database
python cli\memory.py health-check

# Test with verbose output
python cli\run_ingestion.py --video "test.mp4" --verbose
```

### Querying Workflow
```powershell
# Check what's in the graph
python cli\graph_query.py stats

# Find specific entities
python cli\graph_query.py list-entities --type person

# Semantic search
python cli\retrieve.py --query "birthday party"

# Natural language query
python cli\nl_query.py
```

---

## Configuration

All CLI tools respect configuration in:
- `<project_root>\config.yaml` - Main configuration
- `<project_root>\config.json` - Legacy configuration
- Environment variables - Runtime overrides

Common configuration paths used by CLI:
```yaml
paths:
  data_dir: "<GOODQ_DATA_ROOT>/GoodQ_Data"
  db_path: "<GOODQ_DATA_ROOT>/GoodQ_Data/databases/goodq.db"
  knowledge_graph_db: "<GOODQ_DATA_ROOT>/GoodQ_Data/knowledge_graph.db"
  log_dir: "<GOODQ_DATA_ROOT>/GoodQ_Data/logs"
  inbox: "<project_root>/import_inbox"
```

---

## Error Handling

### Common Issues

**"Database locked"**
```powershell
# Close all Python processes
taskkill /F /IM python.exe

# Restart command
```

**"LLM not available"**
```powershell
# Ensure LM Studio or Ollama is running
# Check llm.api_url in config.yaml
```

**"Model not found"**
```powershell
# Verify models exist
dir <GOODQ_DATA_ROOT>\models\

# Check model paths in config
python cli\print_config.py | grep models
```

**"Out of VRAM"**
```powershell
# Check GPU usage
nvidia-smi

# Reduce batch sizes in config or close other GPU processes
```

---

## See Also

- [CHEAT_SHEET.md](../../CHEAT_SHEET.md) - Quick command reference
- [USER_GUIDE.md](../../guides/general/USER_GUIDE.md) - Comprehensive user guide
- [QUICK_START.md](../../QUICK_START.md) - Getting started
- [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md) - Detailed troubleshooting
- [Knowledge Graph Documentation](../../technical/knowledge_graph.md) - Graph schema and queries

---

**Last Updated:** 2025-12-15  
**Status:** Complete ✅
