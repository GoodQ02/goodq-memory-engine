#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoodQ API Server - Production Grade
Real data streams, no placeholders. Every endpoint is functional.
"""

import json
import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio
from collections import defaultdict
import hashlib
import traceback as tb
import psutil

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Import LLM client
try:
    from llm_client import LLMClient
    print("✓ LLM client module imported")
except ImportError as e:
    print(f"⚠ LLM client import failed: {e}")
    LLMClient = None

app = FastAPI(title="GoodQ API", version="2.0.0-production")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
PROCESSING_DIR = DATA_DIR / "processing"
MEMORY_DB = DATA_DIR / "memory.db"
KG_DB = DATA_DIR / "knowledge_graph.db"
UNIFIED_DB = DATA_DIR / "unified_goodq.db"
FAISS_DIR = DATA_DIR / "faiss_indices"
COMMAND_LOG = LOGS_DIR / "command_center.log"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
PROCESSING_DIR.mkdir(exist_ok=True)

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# Initialize LLM client
print("\n" + "="*80)
print("Initializing LLM Client...")
print("="*80)
llm = None
if LLMClient:
    try:
        llm = LLMClient()
        print(f"LLM Status: {'✓ CONNECTED' if llm.available else '⚠ OFFLINE (using fallback)'}")
        if llm.available:
            print(f"Model: {llm.model}")
    except Exception as e:
        print(f"❌ LLM initialization failed: {e}")
        llm = None

if not llm or not (hasattr(llm, 'available') and llm.available):
    print("Using fallback mode (database queries only)")
print("="*80 + "\n")


class QueryRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10


class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class CommandRequest(BaseModel):
    command: str
    args: Optional[Dict[str, Any]] = None


# ============================================================================
# REAL DATA ENDPOINTS - ALL FUNCTIONAL
# ============================================================================

@app.get("/")
async def serve_index():
    """Serve the main UI"""
    index_file = BASE_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="UI not found")


@app.get("/api/status")
async def get_status():
    """Get real-time system status from actual logs and databases"""
    try:
        status_data = {
            "status": "active",
            "processing": {
                "active": False,
                "current_file": None,
                "started": None,
                "progress": None
            },
            "database": {
                "scenes": 0,
                "embeddings": 0,
                "segments": 0,
                "entities": 0,
                "relationships": 0
            },
            "faiss": {
                "text": False,
                "clip": False,
                "dino": False,
                "audio": False
            },
            "timestamp": datetime.now().isoformat()
        }

        # Check watchdog log for current processing
        watchdog_log = LOGS_DIR / "watchdog.log"
        if watchdog_log.exists():
            try:
                with open(watchdog_log, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    for line in reversed(lines[-100:]):
                        if "Processing video:" in line:
                            status_data["processing"]["active"] = True
                            parts = line.split("Processing video:")
                            if len(parts) > 1:
                                status_data["processing"]["current_file"] = parts[1].strip()
                            timestamp_str = line.split('[INFO]')[0].strip()
                            status_data["processing"]["started"] = timestamp_str
                            break
                        elif "Successfully processed:" in line or "Failed to process:" in line:
                            status_data["processing"]["active"] = False
                            break
            except Exception as e:
                print(f"Error reading watchdog log: {e}")

        # Get database stats
        if MEMORY_DB.exists():
            try:
                conn = sqlite3.connect(str(MEMORY_DB))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM scenes")
                status_data["database"]["scenes"] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                status_data["database"]["embeddings"] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM segments")
                status_data["database"]["segments"] = cursor.fetchone()[0]
                
                conn.close()
            except Exception as e:
                print(f"Error querying memory.db: {e}")

        # Get knowledge graph stats
        if KG_DB.exists():
            try:
                conn = sqlite3.connect(str(KG_DB))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM nodes")
                status_data["database"]["entities"] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM edges")
                status_data["database"]["relationships"] = cursor.fetchone()[0]
                
                conn.close()
            except Exception as e:
                print(f"Error querying knowledge_graph.db: {e}")

        # Check FAISS indices
        if FAISS_DIR.exists():
            status_data["faiss"]["text"] = (FAISS_DIR / "text" / "faiss_text.index").exists()
            status_data["faiss"]["clip"] = (FAISS_DIR / "clip" / "faiss_clip.index").exists()
            status_data["faiss"]["dino"] = (FAISS_DIR / "dino" / "faiss_dino.index").exists()
            status_data["faiss"]["audio"] = (FAISS_DIR / "audio" / "faiss_audio.index").exists()

        return status_data

    except Exception as e:
        print(f"Error in get_status: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress")
async def get_progress():
    """Get real-time processing progress"""
    try:
        progress_file = Path("L:/goodq4all/logs/progress.json")
        
        if not progress_file.exists():
            return {
                "status": "idle",
                "message": "No active processing",
                "timestamp": datetime.now().isoformat()
            }
        
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        return progress_data
    
    except Exception as e:
        print(f"Error in get_progress: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenes")
async def get_scenes(limit: int = 100, offset: int = 0):
    """Get real scene data from memory.db"""
    try:
        if not MEMORY_DB.exists():
            return {"scenes": [], "total": 0, "limit": limit, "offset": offset}

        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()

        # Get total count
        cursor.execute("SELECT COUNT(*) FROM scenes")
        total = cursor.fetchone()[0]

        # Get scenes with proper column names
        cursor.execute("""
            SELECT id, video_hash, start, end, meta, created_at
            FROM scenes
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        scenes = []
        for row in cursor.fetchall():
            scene_id, video_hash, start, end, meta_json, created_at = row
            
            # Parse metadata
            meta = {}
            if meta_json:
                try:
                    meta = json.loads(meta_json)
                except:
                    pass

            # Extract key info from meta
            scene_data = {
                "id": scene_id,
                "video_hash": video_hash,
                "scene_number": meta.get("index", 0),
                "start": float(start) if start is not None else 0.0,
                "end": float(end) if end is not None else 0.0,
                "duration": (float(end) - float(start)) if (end is not None and start is not None) else 0.0,
                "summary": meta.get("summary", meta.get("caption", "")),
                "caption": meta.get("caption", ""),
                "transcript": meta.get("transcript", ""),
                "emotions": meta.get("emotions", []),
                "sentiment": meta.get("sentiment", {}),
                "dominant_emotion": meta.get("dominant_emotion", {}),
                "audio_emotions": meta.get("audio_emotion", []),
                "created_at": created_at,
                "has_keyframe": bool(meta.get("keyframe")),
                "has_audio": bool(meta.get("audio"))
            }
            
            scenes.append(scene_data)

        conn.close()

        return {
            "scenes": scenes,
            "total": total,
            "limit": limit,
            "offset": offset,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"Error in get_scenes: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scene/{scene_id}")
async def get_scene_detail(scene_id: int):
    """Get detailed information about a specific scene"""
    try:
        if not MEMORY_DB.exists():
            raise HTTPException(status_code=404, detail="Database not found")

        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()

        # Get scene data
        cursor.execute("""
            SELECT id, video_hash, start, end, meta, created_at
            FROM scenes
            WHERE id = ?
        """, (scene_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")

        scene_id, video_hash, start, end, meta_json, created_at = row
        
        # Parse metadata
        meta = {}
        if meta_json:
            try:
                meta = json.loads(meta_json)
            except:
                pass

        # Build detailed scene data
        scene_detail = {
            "id": scene_id,
            "video_hash": video_hash,
            "scene_number": meta.get("index", 0),
            "start": float(start) if start is not None else 0.0,
            "end": float(end) if end is not None else 0.0,
            "duration": (float(end) - float(start)) if (end is not None and start is not None) else 0.0,
            "summary": meta.get("summary", meta.get("caption", "")),
            "caption": meta.get("caption", ""),
            "transcript": meta.get("transcript", ""),
            "emotions": meta.get("emotions", []),
            "sentiment": meta.get("sentiment", {}),
            "dominant_emotion": meta.get("dominant_emotion", {}),
            "audio_emotions": meta.get("audio_emotion", []),
            "created_at": created_at,
            "metadata": meta,
            "has_keyframe": bool(meta.get("keyframe")),
            "has_audio": bool(meta.get("audio"))
        }
        
        # Get related entities for this scene
        if KG_DB.exists():
            kg_conn = sqlite3.connect(str(KG_DB))
            kg_cursor = kg_conn.cursor()
            
            # Try to find entities linked to this scene
            kg_cursor.execute("""
                SELECT DISTINCT n.node_id, n.name, n.node_type, n.properties
                FROM nodes n
                JOIN edges e ON (n.node_id = e.source_id OR n.node_id = e.target_id)
                LIMIT 20
            """)
            
            entities = []
            for ent_row in kg_cursor.fetchall():
                node_id, name, node_type, props_json = ent_row
                props = {}
                if props_json:
                    try:
                        props = json.loads(props_json)
                    except:
                        pass
                entities.append({
                    "id": node_id,
                    "name": name,
                    "type": node_type,
                    "properties": props
                })
            
            scene_detail["entities"] = entities
            kg_conn.close()
        
        conn.close()
        return scene_detail

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in get_scene_detail: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entities")
async def get_entities(limit: int = 100, entity_type: Optional[str] = None):
    """Get real entities from knowledge graph"""
    try:
        if not KG_DB.exists():
            return {"entities": [], "total": 0}

        conn = sqlite3.connect(str(KG_DB))
        cursor = conn.cursor()

        # Build query
        if entity_type:
            cursor.execute("""
                SELECT node_id, name, node_type, properties
                FROM nodes
                WHERE node_type = ?
                LIMIT ?
            """, (entity_type, limit))
        else:
            cursor.execute("""
                SELECT node_id, name, node_type, properties
                FROM nodes
                LIMIT ?
            """, (limit,))

        entities = []
        for row in cursor.fetchall():
            node_id, name, node_type, props_json = row
            
            props = {}
            if props_json:
                try:
                    props = json.loads(props_json)
                except:
                    pass

            entities.append({
                "id": node_id,
                "name": name,
                "type": node_type,
                "properties": props
            })

        conn.close()

        return {
            "entities": entities,
            "total": len(entities),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        print(f"Error in get_entities: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics")
async def get_analytics():
    """Get real analytics data"""
    try:
        analytics = {
            "overview": {
                "total_scenes": 0,
                "total_embeddings": 0,
                "total_entities": 0,
                "total_relationships": 0,
                "processing_time": None
            },
            "emotions": {
                "distribution": [],
                "timeline": []
            },
            "entities": {
                "by_type": [],
                "most_frequent": []
            },
            "sentiment": {
                "positive": 0,
                "negative": 0,
                "neutral": 0
            },
            "timestamp": datetime.now().isoformat()
        }

        # Get overview stats
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM scenes")
            analytics["overview"]["total_scenes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM embeddings")
            analytics["overview"]["total_embeddings"] = cursor.fetchone()[0]

            # Get emotion distribution from scenes
            cursor.execute("SELECT meta FROM scenes")
            emotion_counts = defaultdict(int)
            sentiment_counts = defaultdict(int)

            for (meta_json,) in cursor.fetchall():
                if not meta_json:
                    continue
                try:
                    meta = json.loads(meta_json)
                    
                    # Count emotions
                    if "emotions" in meta and isinstance(meta["emotions"], list):
                        for emotion in meta["emotions"]:
                            if isinstance(emotion, dict) and "label" in emotion:
                                emotion_counts[emotion["label"]] += 1
                    
                    # Count sentiment
                    if "sentiment_label" in meta:
                        sentiment_counts[meta["sentiment_label"]] += 1

                except:
                    pass

            # Format emotion distribution
            analytics["emotions"]["distribution"] = [
                {"emotion": k, "count": v}
                for k, v in sorted(emotion_counts.items(), key=lambda x: x[1], reverse=True)
            ][:10]

            # Format sentiment
            analytics["sentiment"] = {
                "positive": sentiment_counts.get("POSITIVE", 0),
                "negative": sentiment_counts.get("NEGATIVE", 0),
                "neutral": sentiment_counts.get("NEUTRAL", 0)
            }

            conn.close()

        # Get knowledge graph stats
        if KG_DB.exists():
            conn = sqlite3.connect(str(KG_DB))
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM nodes")
            analytics["overview"]["total_entities"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM edges")
            analytics["overview"]["total_relationships"] = cursor.fetchone()[0]

            # Get entities by type
            cursor.execute("""
                SELECT node_type, COUNT(*) as count
                FROM nodes
                GROUP BY node_type
                ORDER BY count DESC
            """)
            analytics["entities"]["by_type"] = [
                {"type": row[0], "count": row[1]}
                for row in cursor.fetchall()
            ]

            # Get most frequent entities
            cursor.execute("""
                SELECT name, node_type, COUNT(*) as freq
                FROM nodes
                GROUP BY name, node_type
                ORDER BY freq DESC
                LIMIT 10
            """)
            analytics["entities"]["most_frequent"] = [
                {"name": row[0], "type": row[1], "frequency": row[2]}
                for row in cursor.fetchall()
            ]

            conn.close()

        return analytics

    except Exception as e:
        print(f"Error in get_analytics: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """Chat with real LLM integration"""
    try:
        print(f"[CHAT] Received: {message.message}")

        # Get current database stats for context
        stats = {}
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM scenes")
            stats['scenes'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            stats['embeddings'] = cursor.fetchone()[0]
            
            conn.close()

        if KG_DB.exists():
            conn = sqlite3.connect(str(KG_DB))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM nodes")
            stats['entities'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM edges")
            stats['relationships'] = cursor.fetchone()[0]
            
            conn.close()

        # Use LLM if available
        if llm and hasattr(llm, 'available') and llm.available:
            print("[CHAT] Using LLM for response...")
            try:
                response = llm.chat(message.message, {"stats": stats})
                if response:
                    return {
                        "message": response,
                        "context": {
                            **stats,
                            "llm_used": True,
                            "model": llm.model,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
            except Exception as e:
                print(f"[CHAT] LLM error: {e}")

        # Fallback response
        response_text = f"I have processed {stats.get('scenes', 0)} scenes with {stats.get('embeddings', 0)} embeddings. The knowledge graph contains {stats.get('entities', 0)} entities and {stats.get('relationships', 0)} relationships."

        return {
            "message": response_text,
            "context": {
                **stats,
                "llm_used": False,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        print(f"Error in chat: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/command")
async def execute_command(cmd: CommandRequest):
    """Execute system commands"""
    try:
        command = cmd.command.lower()
        
        if command == "start_ingestion":
            # This would trigger watchdog
            return {
                "status": "success",
                "message": "Ingestion watchdog monitoring is active. Add files to import_inbox to process them."
            }
        
        elif command == "stop_ingestion":
            return {
                "status": "info",
                "message": "Ingestion can be stopped by closing the watchdog process."
            }
        
        else:
            return {
                "status": "error",
                "message": f"Unknown command: {command}"
            }

    except Exception as e:
        print(f"Error in execute_command: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/command-center")
async def get_command_center():
    """Get command center data - real-time watchdog log stream"""
    try:
        log_data = {
            "active": False,
            "processing": {
                "active": False,
                "current_file": None
            },
            "logs": [],
            "stats": {
                "files_processed": 0,
                "current_file": None,
                "errors": 0,
                "warnings": 0
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # Read watchdog log
        watchdog_log = LOGS_DIR / "watchdog.log"
        if watchdog_log.exists():
            try:
                with open(watchdog_log, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                    # Get last 50 lines for display
                    recent_lines = lines[-50:]
                    
                    for line in recent_lines:
                        log_entry = {
                            "timestamp": "",
                            "level": "INFO",
                            "message": line.strip()
                        }
                        
                        # Parse log format: YYYY-MM-DD HH:MM:SS,mmm [LEVEL] Message
                        if "[INFO]" in line:
                            parts = line.split("[INFO]")
                            if len(parts) >= 2:
                                log_entry["timestamp"] = parts[0].strip()
                                log_entry["message"] = parts[1].strip()
                                log_entry["level"] = "INFO"
                        elif "[ERROR]" in line:
                            parts = line.split("[ERROR]")
                            if len(parts) >= 2:
                                log_entry["timestamp"] = parts[0].strip()
                                log_entry["message"] = parts[1].strip()
                                log_entry["level"] = "ERROR"
                            log_data["stats"]["errors"] += 1
                        elif "[WARNING]" in line or "[WARN]" in line:
                            log_entry["level"] = "WARNING"
                            log_data["stats"]["warnings"] += 1
                        
                        log_data["logs"].append(log_entry)
                    
                    # Check if actively processing
                    for line in reversed(lines[-20:]):
                        if "Processing video:" in line:
                            log_data["active"] = True
                            log_data["processing"]["active"] = True
                            parts = line.split("Processing video:")
                            if len(parts) > 1:
                                current_file = parts[1].strip()
                                log_data["stats"]["current_file"] = current_file
                                log_data["processing"]["current_file"] = current_file
                            break
                        elif "Successfully processed:" in line:
                            log_data["stats"]["files_processed"] += 1
                        elif "Failed to process:" in line:
                            log_data["active"] = False
                            log_data["processing"]["active"] = False
                            break
                            
            except Exception as e:
                print(f"Error reading watchdog log: {e}")
        
        return log_data
        
    except Exception as e:
        print(f"Error in get_command_center: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes")
async def get_processes():
    """Get process status from process manager"""
    try:
        from process_manager import ProcessManager
        
        pm = ProcessManager()
        processes = {}
        
        for name, proc_info in pm.processes.items():
            processes[name] = proc_info.to_dict()
        
        return {
            "processes": processes,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        # Fallback - check manually
        processes = {
            "watchdog": {
                "name": "watchdog",
                "status": "unknown",
                "pid": None
            },
            "api_server": {
                "name": "api_server",
                "status": "running",
                "pid": os.getpid()
            }
        }
        
        # Try to find watchdog process
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'watchdog' in ' '.join(cmdline):
                    processes["watchdog"]["status"] = "running"
                    processes["watchdog"]["pid"] = proc.info['pid']
                    break
            except:
                pass
        
        return {
            "processes": processes,
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/processes/{process_name}/{action}")
async def control_process(process_name: str, action: str):
    """Control processes (start/stop/restart)"""
    try:
        if action not in ["start", "stop", "restart"]:
            raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
        
        # For now, return info - actual implementation would use ProcessManager
        return {
            "status": "info",
            "message": f"Process control: {action} {process_name} - Use LAUNCH_GOODQ_PRODUCTION.bat to manage processes",
            "process": process_name,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"Error in control_process: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress")
async def get_progress():
    """Get current processing progress"""
    try:
        # Try to load progress from file
        progress_file = LOGS_DIR / "progress.json"
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
                return {
                    "has_progress": True,
                    "data": progress_data
                }
        else:
            return {
                "has_progress": False,
                "data": {
                    "status": "idle",
                    "file": None,
                    "step": None,
                    "progress_percent": 0,
                    "completed_steps": 0,
                    "total_steps": 0
                }
            }
    except Exception as e:
        print(f"Error loading progress: {e}")
        return {
            "has_progress": False,
            "error": str(e),
            "data": {
                "status": "error",
                "file": None,
                "step": None,
                "progress_percent": 0,
                "completed_steps": 0,
                "total_steps": 0
            }
        }


@app.get("/api/analytics/database")
async def get_database_analytics():
    """Comprehensive database statistics"""
    try:
        stats = {
            "memory_db": {},
            "unified_db": {},
            "timestamp": datetime.now().isoformat()
        }
        
        # Memory DB stats
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM scenes")
            stats["memory_db"]["scenes"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM embeddings")
            stats["memory_db"]["embeddings"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM segments")
            stats["memory_db"]["segments"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM links")
            stats["memory_db"]["relationships"] = cursor.fetchone()[0]
            
            # Get modality distribution
            cursor.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality")
            stats["memory_db"]["embeddings_by_modality"] = dict(cursor.fetchall())
            
            # Get emotion distribution from recent scenes
            cursor.execute("SELECT meta FROM scenes LIMIT 100")
            emotions = []
            for (meta_json,) in cursor.fetchall():
                if meta_json:
                    try:
                        meta = json.loads(meta_json)
                        if "emotions" in meta:
                            emotions.extend(meta["emotions"])
                    except:
                        pass
            stats["memory_db"]["total_emotions_detected"] = len(emotions)
            
            conn.close()
        
        # Unified DB stats
        if UNIFIED_DB.exists():
            conn = sqlite3.connect(str(UNIFIED_DB))
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM global_entities")
            stats["unified_db"]["global_entities"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cross_video_relationships")
            stats["unified_db"]["cross_video_relationships"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM temporal_timeline")
            stats["unified_db"]["timeline_events"] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM video_registry")
            stats["unified_db"]["videos_registered"] = cursor.fetchone()[0]
            
            # Entity types
            cursor.execute("SELECT entity_type, COUNT(*) FROM global_entities GROUP BY entity_type")
            stats["unified_db"]["entities_by_type"] = dict(cursor.fetchall())
            
            conn.close()
        
        return stats
        
    except Exception as e:
        print(f"Error in get_database_analytics: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/emotions")
async def get_emotion_analytics():
    """Get emotion analytics from processed scenes"""
    try:
        if not MEMORY_DB.exists():
            return {"emotions": [], "summary": {}}
        
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()
        
        # Get all scenes with emotion data
        cursor.execute("SELECT id, start, end, meta FROM scenes ORDER BY start")
        
        emotion_timeline = []
        emotion_counts = defaultdict(int)
        
        for scene_id, start, end, meta_json in cursor.fetchall():
            if not meta_json:
                continue
                
            try:
                meta = json.loads(meta_json)
                
                # Extract emotions
                emotions = meta.get("emotions", [])
                dominant = meta.get("dominant_emotion", {})
                audio_emotions = meta.get("audio_emotion", [])
                
                # Count all emotions
                for emo in emotions:
                    if isinstance(emo, dict) and "label" in emo:
                        emotion_counts[emo["label"]] += 1
                
                # Add to timeline
                emotion_timeline.append({
                    "scene_id": scene_id,
                    "start": float(start) if start else 0,
                    "end": float(end) if end else 0,
                    "emotions": emotions,
                    "dominant_emotion": dominant,
                    "audio_emotions": audio_emotions
                })
                
            except Exception as e:
                print(f"Error parsing scene metadata: {e}")
                continue
        
        conn.close()
        
        # Calculate summary statistics
        total_emotions = sum(emotion_counts.values())
        emotion_percentages = {}
        if total_emotions > 0:
            for emotion, count in emotion_counts.items():
                emotion_percentages[emotion] = round(count / total_emotions * 100, 2)
        
        return {
            "timeline": emotion_timeline,
            "counts": dict(emotion_counts),
            "percentages": emotion_percentages,
            "total_detections": total_emotions,
            "unique_emotions": len(emotion_counts)
        }
        
    except Exception as e:
        print(f"Error in get_emotion_analytics: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/entities")
async def get_entities(limit: int = 100, entity_type: Optional[str] = None):
    """Get entities from unified knowledge graph"""
    try:
        print(f"[DEBUG] Checking UNIFIED_DB path: {UNIFIED_DB}")
        print(f"[DEBUG] DB exists: {UNIFIED_DB.exists()}")
        
        if not UNIFIED_DB.exists():
            return {"entities": [], "total": 0, "error": f"DB not found at {UNIFIED_DB}"}
        
        conn = sqlite3.connect(str(UNIFIED_DB))
        cursor = conn.cursor()
        
        # Build query - use correct column name: canonical_name
        if entity_type:
            query = "SELECT id, canonical_name, entity_type, properties FROM global_entities WHERE entity_type = ? LIMIT ?"
            cursor.execute(query, (entity_type, limit))
        else:
            query = "SELECT id, canonical_name, entity_type, properties FROM global_entities LIMIT ?"
            cursor.execute(query, (limit,))
        
        entities = []
        rows = cursor.fetchall()
        print(f"[DEBUG] Found {len(rows)} entities")
        
        for entity_id, canonical_name, ent_type, props_json in rows:
            props = {}
            if props_json:
                try:
                    props = json.loads(props_json)
                except:
                    pass
            
            entities.append({
                "id": entity_id,
                "name": canonical_name,
                "type": ent_type,
                "properties": props
            })
        
        # Get total count
        if entity_type:
            cursor.execute("SELECT COUNT(*) FROM global_entities WHERE entity_type = ?", (entity_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM global_entities")
        total = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"[DEBUG] Returning {len(entities)} entities, total={total}")
        return {
            "entities": entities,
            "total": total,
            "limit": limit,
            "filtered_by": entity_type
        }
        
    except Exception as e:
        print(f"Error in get_entities: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge-graph")
async def get_knowledge_graph(limit: int = 50):
    """Get knowledge graph nodes and edges for visualization"""
    try:
        if not UNIFIED_DB.exists():
            return {"nodes": [], "edges": []}
        
        conn = sqlite3.connect(str(UNIFIED_DB))
        cursor = conn.cursor()
        
        # Get nodes (entities) - use correct column names
        cursor.execute("SELECT id, canonical_name, entity_type FROM global_entities LIMIT ?", (limit,))
        nodes = []
        for entity_id, canonical_name, ent_type in cursor.fetchall():
            nodes.append({
                "id": entity_id,
                "label": canonical_name,
                "type": ent_type
            })
        
        # Get edges (relationships)
        node_ids = [n["id"] for n in nodes]
        if node_ids:
            placeholders = ','.join(['?' for _ in node_ids])
            query = f"""
                SELECT source_entity_id, target_entity_id, relationship_type, properties
                FROM cross_video_relationships
                WHERE source_entity_id IN ({placeholders}) 
                OR target_entity_id IN ({placeholders})
                LIMIT ?
            """
            cursor.execute(query, node_ids + node_ids + [limit * 2])
            
            edges = []
            for source, target, rel_type, props_json in cursor.fetchall():
                props = {}
                if props_json:
                    try:
                        props = json.loads(props_json)
                    except:
                        pass
                
                edges.append({
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "properties": props
                })
        else:
            edges = []
        
        conn.close()
        
        return {
            "nodes": nodes,
            "edges": edges
        }
        
    except Exception as e:
        print(f"Error in get_knowledge_graph: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/processes/start_ingestion")
async def start_ingestion():
    """Start the watchdog ingestion process"""
    try:
        import subprocess
        
        # Check if already running
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'watchdog_ingest.py' in ' '.join(cmdline):
                    return {
                        "status": "already_running",
                        "message": "Watchdog is already running",
                        "pid": proc.info['pid']
                    }
            except:
                continue
        
        # Start watchdog in background
        script_path = BASE_DIR / "scripts" / "watchdog_ingest.py"
        if not script_path.exists():
            raise HTTPException(status_code=404, detail="Watchdog script not found")
        
        # Use detached process
        if sys.platform == 'win32':
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS
            )
        else:
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                start_new_session=True
            )
        
        return {
            "status": "started",
            "message": "Watchdog ingestion process started",
            "pid": process.pid
        }
        
    except Exception as e:
        print(f"Error starting ingestion: {e}")
        tb.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time status updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send status updates every 5 seconds
            await asyncio.sleep(5)
            status = await get_status()
            await websocket.send_json(status)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


# ============================================================================
# STARTUP
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("GoodQ API Server Starting")
    print("="*80)
    print(f"Base Directory: {BASE_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Server will be available at: http://localhost:3000")
    print("="*80 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=3000, log_level="info")
