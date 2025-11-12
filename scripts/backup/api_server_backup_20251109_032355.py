#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GoodQ API Server - Production Grade Backend
Serves processed video data, knowledge graph queries, and real-time status
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

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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
    print(f"⚠ Installing requests for LLM client...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "--quiet"])
    from llm_client import LLMClient
    print("✓ LLM client module imported after install")

app = FastAPI(title="GoodQ API", version="1.0.0")

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

# WebSocket connections for real-time updates
active_connections: List[WebSocket] = []

# Initialize LLM client
print("\n" + "="*80)
print("Initializing LLM Client...")
print("="*80)
try:
    llm = LLMClient()
    print(f"LLM Status: {'✓ CONNECTED' if llm.available else '⚠ OFFLINE (using fallback)'}")
    if llm.available:
        print(f"Model: {llm.model}")
except Exception as e:
    print(f"❌ LLM initialization failed: {e}")
    import traceback
    traceback.print_exc()
    # Create a dummy LLM for fallback
    class DummyLLM:
        available = False
        model = None
        def chat(self, *args, **kwargs):
            return None
    llm = DummyLLM()
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
    params: Optional[Dict[str, Any]] = None


@app.get("/")
async def root():
    """Serve the main UI"""
    return FileResponse(BASE_DIR / "index.html")


@app.get("/scenes.html")
async def scenes_page():
    """Serve the Scene Explorer page"""
    return FileResponse(BASE_DIR / "scenes.html")


@app.get("/simple_chat_test.html")
async def simple_test():
    """Serve the simple chat test page"""
    return FileResponse(BASE_DIR / "simple_chat_test.html")


@app.get("/test_chat_debug.html")
async def test_debug():
    """Serve the debug test page"""
    return FileResponse(BASE_DIR / "test_chat_debug.html")


@app.get("/dashboard.html")
async def dashboard():
    """Serve the dashboard"""
    return FileResponse(BASE_DIR / "dashboard.html")


@app.get("/api/scenes")
async def get_scenes():
    """Get all scenes from memory database"""
    try:
        if not MEMORY_DB.exists():
            return {"scenes": [], "count": 0, "error": "Memory database not found"}
        
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()
        
        try:
            # Get all scenes with metadata
            cursor.execute("""
                SELECT 
                    s.id,
                    s.video_hash,
                    s.start,
                    s.end,
                    s.meta,
                    s.created_at,
                    COUNT(DISTINCT e.hash) as embedding_count,
                    GROUP_CONCAT(DISTINCT e.modality) as modalities
                FROM scenes s
                LEFT JOIN embeddings e ON s.id = e.scene_id
                GROUP BY s.id
                ORDER BY s.start
            """)
            
            scenes = []
            for row in cursor.fetchall():
                scene_id, video_hash, start, end, meta_json, created_at, emb_count, modalities = row
                
                # Parse metadata
                meta = {}
                if meta_json:
                    try:
                        meta = json.loads(meta_json)
                    except:
                        pass
                
                scenes.append({
                    "id": scene_id,
                    "video_hash": video_hash,
                    "start": start,
                    "end": end,
                    "duration": end - start if (end and start) else 0,
                    "meta": meta,
                    "created_at": created_at,
                    "embedding_count": emb_count or 0,
                    "modalities": modalities.split(',') if modalities else []
                })
            
            return {
                "scenes": scenes,
                "count": len(scenes),
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[API] Error getting scenes: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenes/{scene_id}")
async def get_scene_detail(scene_id: str):
    """Get detailed information for a specific scene"""
    try:
        if not MEMORY_DB.exists():
            raise HTTPException(status_code=404, detail="Memory database not found")
        
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()
        
        try:
            # Get scene info
            cursor.execute("""
                SELECT id, video_hash, start, end, meta, created_at
                FROM scenes
                WHERE id = ?
            """, (scene_id,))
            
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            
            scene_id, video_hash, start, end, meta_json, created_at = row
            
            # Parse metadata
            meta = {}
            if meta_json:
                try:
                    meta = json.loads(meta_json)
                except:
                    pass
            
            # Get embeddings breakdown
            cursor.execute("""
                SELECT modality, COUNT(*) as count
                FROM embeddings
                WHERE scene_id = ?
                GROUP BY modality
            """, (scene_id,))
            
            embeddings = {}
            for mod, count in cursor.fetchall():
                embeddings[mod] = count
            
            # Get segments for this scene
            cursor.execute("""
                SELECT id, start, end, speaker, meta
                FROM segments
                WHERE video_hash = ? AND start >= ? AND end <= ?
                ORDER BY start
            """, (video_hash, start, end))
            
            segments = []
            for seg_id, seg_start, seg_end, speaker, seg_meta_json in cursor.fetchall():
                seg_meta = {}
                if seg_meta_json:
                    try:
                        seg_meta = json.loads(seg_meta_json)
                    except:
                        pass
                
                segments.append({
                    "id": seg_id,
                    "start": seg_start,
                    "end": seg_end,
                    "duration": seg_end - seg_start if (seg_end and seg_start) else 0,
                    "speaker": speaker,
                    "meta": seg_meta
                })
            
            return {
                "scene": {
                    "id": scene_id,
                    "video_hash": video_hash,
                    "start": start,
                    "end": end,
                    "duration": end - start if (end and start) else 0,
                    "meta": meta,
                    "created_at": created_at,
                    "embeddings": embeddings,
                    "embedding_count": sum(embeddings.values()),
                    "segments": segments,
                    "segment_count": len(segments)
                },
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error getting scene detail: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenes/{scene_id}/emotions")
async def get_scene_emotions(scene_id: str):
    """Get emotion data for a specific scene"""
    try:
        if not MEMORY_DB.exists():
            raise HTTPException(status_code=404, detail="Memory database not found")
        
        conn = sqlite3.connect(str(MEMORY_DB))
        cursor = conn.cursor()
        
        try:
            # Verify scene exists
            cursor.execute("SELECT id FROM scenes WHERE id = ?", (scene_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Scene {scene_id} not found")
            
            # Get emotion data from embeddings
            cursor.execute("""
                SELECT 
                    emotions_json,
                    sentiment_label,
                    sentiment_score,
                    modality
                FROM embeddings
                WHERE scene_id = ?
                AND (emotions_json IS NOT NULL OR sentiment_label IS NOT NULL)
            """, (scene_id,))
            
            emotion_data = []
            sentiment_counts = {}
            emotion_counts = {}
            
            for emotions_json, sentiment_label, sentiment_score, modality in cursor.fetchall():
                # Parse emotions
                emotions = []
                if emotions_json:
                    try:
                        emotions = json.loads(emotions_json)
                    except:
                        pass
                
                # Track emotions
                if isinstance(emotions, list):
                    for emotion in emotions:
                        if isinstance(emotion, dict) and 'label' in emotion:
                            label = emotion['label']
                            emotion_counts[label] = emotion_counts.get(label, 0) + 1
                
                # Track sentiment
                if sentiment_label:
                    sentiment_counts[sentiment_label] = sentiment_counts.get(sentiment_label, 0) + 1
                
                emotion_data.append({
                    "modality": modality,
                    "emotions": emotions,
                    "sentiment": {
                        "label": sentiment_label,
                        "score": sentiment_score
                    }
                })
            
            # Get top emotions
            top_emotions = sorted(
                [{"emotion": k, "count": v} for k, v in emotion_counts.items()],
                key=lambda x: x['count'],
                reverse=True
            )[:5]
            
            # Get sentiment breakdown
            sentiment_breakdown = [
                {"sentiment": k, "count": v}
                for k, v in sentiment_counts.items()
            ]
            
            return {
                "scene_id": scene_id,
                "emotion_data": emotion_data,
                "top_emotions": top_emotions,
                "sentiment_breakdown": sentiment_breakdown,
                "total_emotion_instances": sum(emotion_counts.values()),
                "timestamp": datetime.now().isoformat()
            }
            
        finally:
            conn.close()
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error getting scene emotions: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """Get overall system status"""
    try:
        # Check watchdog log for current processing
        watchdog_log = LOGS_DIR / "watchdog.log"
        processing_status = {"active": False, "current_file": None, "started": None}
        
        if watchdog_log.exists():
            with open(watchdog_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                for line in reversed(lines[-100:]):
                    if "Processing video:" in line:
                        processing_status["active"] = True
                        parts = line.split("Processing video:")
                        if len(parts) > 1:
                            processing_status["current_file"] = parts[1].strip()
                        # Extract timestamp
                        timestamp_str = line.split('[INFO]')[0].strip()
                        processing_status["started"] = timestamp_str
                        break
                    elif "Successfully processed:" in line or "Failed to process:" in line:
                        processing_status["active"] = False
                        break
        
        # Count available videos
        video_count = 0
        if OUTPUT_DIR.exists():
            video_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
            video_count = len(video_dirs)
        
        # Check Neo4j data
        neo4j_dir = DATA_DIR / "neo4j"
        neo4j_active = neo4j_dir.exists() and any(neo4j_dir.iterdir())
        
        return {
            "status": "active" if processing_status["active"] else "ready",
            "processing": processing_status,
            "videos_processed": video_count,
            "knowledge_graph_active": neo4j_active,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos")
async def list_videos():
    """List all processed videos"""
    try:
        videos = []
        
        if not OUTPUT_DIR.exists():
            return {"videos": [], "count": 0}
        
        for video_dir in OUTPUT_DIR.iterdir():
            if not video_dir.is_dir():
                continue
            
            # Get metadata
            metadata_file = video_dir / "metadata.json"
            metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            
            # Count scenes
            scenes_dir = video_dir / "scenes"
            scene_count = 0
            if scenes_dir.exists():
                scene_count = len([f for f in scenes_dir.iterdir() if f.is_dir()])
            
            # Get processing stats
            stats = {
                "scenes": scene_count,
                "has_transcript": (video_dir / "transcript.json").exists(),
                "has_embeddings": (video_dir / "embeddings").exists(),
                "has_analysis": (video_dir / "analysis.json").exists(),
            }
            
            videos.append({
                "id": video_dir.name,
                "name": metadata.get("original_filename", video_dir.name),
                "duration": metadata.get("duration"),
                "processed_date": metadata.get("processed_date"),
                "stats": stats,
                "metadata": metadata
            })
        
        videos.sort(key=lambda x: x.get("processed_date", ""), reverse=True)
        
        return {
            "videos": videos,
            "count": len(videos)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}")
async def get_video_details(video_id: str):
    """Get detailed information about a specific video"""
    try:
        video_dir = OUTPUT_DIR / video_id
        if not video_dir.exists():
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Load all available data
        data = {
            "id": video_id,
            "metadata": {},
            "transcript": None,
            "scenes": [],
            "analysis": None,
            "entities": [],
            "emotions": [],
            "relationships": []
        }
        
        # Metadata
        metadata_file = video_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                data["metadata"] = json.load(f)
        
        # Transcript
        transcript_file = video_dir / "transcript.json"
        if transcript_file.exists():
            with open(transcript_file, 'r', encoding='utf-8') as f:
                data["transcript"] = json.load(f)
        
        # Scenes
        scenes_dir = video_dir / "scenes"
        if scenes_dir.exists():
            for scene_dir in sorted(scenes_dir.iterdir()):
                if not scene_dir.is_dir():
                    continue
                
                scene_data = {"id": scene_dir.name, "frames": []}
                
                # Scene metadata
                scene_meta_file = scene_dir / "scene_metadata.json"
                if scene_meta_file.exists():
                    with open(scene_meta_file, 'r', encoding='utf-8') as f:
                        scene_data.update(json.load(f))
                
                # Scene analysis
                analysis_file = scene_dir / "analysis.json"
                if analysis_file.exists():
                    with open(analysis_file, 'r', encoding='utf-8') as f:
                        scene_data["analysis"] = json.load(f)
                
                data["scenes"].append(scene_data)
        
        # Analysis
        analysis_file = video_dir / "analysis.json"
        if analysis_file.exists():
            with open(analysis_file, 'r', encoding='utf-8') as f:
                data["analysis"] = json.load(f)
        
        # Entities (from knowledge graph extraction)
        entities_file = video_dir / "entities.json"
        if entities_file.exists():
            with open(entities_file, 'r', encoding='utf-8') as f:
                data["entities"] = json.load(f)
        
        # Emotions
        emotions_file = video_dir / "emotions.json"
        if emotions_file.exists():
            with open(emotions_file, 'r', encoding='utf-8') as f:
                data["emotions"] = json.load(f)
        
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}/scenes/{scene_id}")
async def get_scene_details(video_id: str, scene_id: str):
    """Get detailed scene information"""
    try:
        scene_dir = OUTPUT_DIR / video_id / "scenes" / scene_id
        if not scene_dir.exists():
            raise HTTPException(status_code=404, detail="Scene not found")
        
        scene_data = {
            "id": scene_id,
            "video_id": video_id,
            "frames": [],
            "analysis": None,
            "transcript": None
        }
        
        # Scene metadata
        meta_file = scene_dir / "scene_metadata.json"
        if meta_file.exists():
            with open(meta_file, 'r', encoding='utf-8') as f:
                scene_data.update(json.load(f))
        
        # Analysis
        analysis_file = scene_dir / "analysis.json"
        if analysis_file.exists():
            with open(analysis_file, 'r', encoding='utf-8') as f:
                scene_data["analysis"] = json.load(f)
        
        # Get frame data
        frames_dir = scene_dir / "frames"
        if frames_dir.exists():
            for frame_file in sorted(frames_dir.glob("*.jpg")):
                scene_data["frames"].append({
                    "filename": frame_file.name,
                    "path": f"/api/videos/{video_id}/scenes/{scene_id}/frames/{frame_file.name}"
                })
        
        return scene_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search")
async def search(request: QueryRequest):
    """Search across all processed videos"""
    try:
        results = []
        query_lower = request.query.lower()
        
        if not OUTPUT_DIR.exists():
            return {"results": [], "count": 0}
        
        for video_dir in OUTPUT_DIR.iterdir():
            if not video_dir.is_dir():
                continue
            
            # Search in transcript
            transcript_file = video_dir / "transcript.json"
            if transcript_file.exists():
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)
                    if isinstance(transcript, dict):
                        text = transcript.get("text", "")
                    elif isinstance(transcript, list):
                        text = " ".join([seg.get("text", "") for seg in transcript])
                    else:
                        text = str(transcript)
                    
                    if query_lower in text.lower():
                        results.append({
                            "type": "transcript",
                            "video_id": video_dir.name,
                            "content": text[:500],
                            "relevance": text.lower().count(query_lower)
                        })
            
            # Search in analysis
            analysis_file = video_dir / "analysis.json"
            if analysis_file.exists():
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    analysis = json.load(f)
                    analysis_str = json.dumps(analysis).lower()
                    if query_lower in analysis_str:
                        results.append({
                            "type": "analysis",
                            "video_id": video_dir.name,
                            "content": analysis,
                            "relevance": analysis_str.count(query_lower)
                        })
        
        # Sort by relevance
        results.sort(key=lambda x: x.get("relevance", 0), reverse=True)
        
        # Apply limit
        results = results[:request.limit]
        
        return {
            "results": results,
            "count": len(results),
            "query": request.query
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """Chat interface - NOW WITH REAL LLM!"""
    try:
        # Log the incoming request for debugging
        print(f"[CHAT] Received message: {message.message}")
        print(f"[CHAT] Context: {message.context}")
        
        query = message.message.lower()
        
        # Query actual data from databases
        stats = {}
        db_insights = []
        
        # Get data from memory.db
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            try:
                # Get counts
                cursor.execute("SELECT COUNT(*) FROM scenes")
                stats['scenes'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                stats['embeddings'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM segments")
                stats['segments'] = cursor.fetchone()[0]
                
            finally:
                conn.close()
        
        # Get data from knowledge graph
        if KG_DB.exists():
            conn = sqlite3.connect(str(KG_DB))
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT COUNT(*) FROM nodes")
                stats['entities'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM edges")
                stats['relationships'] = cursor.fetchone()[0]
                
            finally:
                conn.close()
        
        # NOW USE LLM FOR INTELLIGENT RESPONSE!
        if llm.available:
            print("[CHAT] 🤖 Using LM Studio for response...")
            
            # Check if user is asking for specific data that requires database query
            query_lower = query
            needs_real_data = any(word in query_lower for word in [
                'pull', 'show me', 'list', 'get', 'find', 'search', 
                'who', 'what entities', 'names', 'people', 'specific'
            ])
            
            # If they want real data, query the database
            real_data = {}
            if needs_real_data:
                print("[CHAT] 📊 Querying database for real data...")
                
                # Get actual entities from knowledge graph
                if KG_DB.exists():
                    conn = sqlite3.connect(str(KG_DB))
                    cursor = conn.cursor()
                    try:
                        # Get top entities
                        cursor.execute("""
                            SELECT name, node_type, COUNT(*) as freq
                            FROM nodes
                            GROUP BY name, node_type
                            ORDER BY freq DESC
                            LIMIT 5
                        """)
                        entities = cursor.fetchall()
                        if entities:
                            real_data['top_entities'] = [
                                {"name": e[0], "type": e[1], "frequency": e[2]} 
                                for e in entities
                            ]
                            print(f"[CHAT] Found {len(entities)} real entities")
                        
                        # Get scene info
                        if MEMORY_DB.exists():
                            mem_conn = sqlite3.connect(str(MEMORY_DB))
                            mem_cursor = mem_conn.cursor()
                            try:
                                mem_cursor.execute("""
                                    SELECT scene_id, video_path, start_time, end_time
                                    FROM scenes
                                    ORDER BY start_time
                                    LIMIT 3
                                """)
                                scenes = mem_cursor.fetchall()
                                if scenes:
                                    real_data['sample_scenes'] = [
                                        {
                                            "id": s[0],
                                            "video": s[1],
                                            "start": s[2],
                                            "end": s[3]
                                        }
                                        for s in scenes
                                    ]
                            finally:
                                mem_conn.close()
                    finally:
                        conn.close()
            
            # Build context for LLM with REAL data
            llm_context = {
                "database_stats": stats,
                "user_query": message.message,
                "processing_status": "Active - processing 1987_1988.mp4 (family home movie from birth year!)",
                "real_data_available": real_data if real_data else "User asked general question, no specific data queried"
            }
            
            # Get LLM response
            llm_response = llm.chat(message.message, llm_context)
            
            if llm_response:
                print(f"[CHAT] ✓ LLM responded: {llm_response[:100]}...")
                return {
                    "message": llm_response,
                    "context": {
                        **stats,
                        "timestamp": datetime.now().isoformat(),
                        "llm_used": True,
                        "model": llm.model,
                        "real_data_queried": bool(real_data)
                    },
                    "suggestions": [
                        "Tell me more about the scenes",
                        "What's actually in the knowledge graph?",
                        "Show me real entity data",
                        "When will processing finish?"
                    ]
                }
        
        # FALLBACK: Database-only response (if LLM unavailable)
        print("[CHAT] ⚠ Using fallback database response...")
        
        # Build response from database
        response_parts = []
        
        if 'scene' in query or 'how many' in query:
            response_parts.append(f"I've identified {stats.get('scenes', 0)} distinct scenes in your videos")
        
        if 'emotion' in query or 'feel' in query:
            response_parts.append(f"I have {stats.get('embeddings', 0)} emotional embeddings captured")
        
        if 'graph' in query or 'knowledge' in query or 'entities' in query:
            response_parts.append(f"Your knowledge graph contains {stats.get('entities', 0)} entities connected by {stats.get('relationships', 0)} relationships")
        
        if not response_parts:
            response_parts.append(f"I have processed {stats.get('scenes', 0)} scenes with {stats.get('embeddings', 0)} embeddings and identified {stats.get('entities', 0)} entities")
        
        return {
            "message": ". ".join(response_parts) + ".",
            "context": {
                **stats,
                "timestamp": datetime.now().isoformat(),
                "llm_used": False
            },
            "suggestions": [
                "Show me emotional moments",
                "What entities do you know about?",
                "Tell me about the scenes",
                "Search for specific content"
            ]
        }
        
    except Exception as e:
        print(f"[CHAT] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
        # Query actual data
        stats = {}
        insights = []
        
        # Get data from memory.db
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            
            try:
                # Get counts
                cursor.execute("SELECT COUNT(*) FROM scenes")
                stats['scenes'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                stats['embeddings'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM segments")
                stats['segments'] = cursor.fetchone()[0]
                
                # Search for emotional content
                if any(word in query for word in ['emotion', 'feel', 'happy', 'sad', 'mood']):
                    cursor.execute("""
                        SELECT DISTINCT sentiment_label, COUNT(*) as count 
                        FROM embeddings 
                        WHERE sentiment_label IS NOT NULL 
                        GROUP BY sentiment_label 
                        ORDER BY count DESC LIMIT 5
                    """)
                    emotions = cursor.fetchall()
                    if emotions:
                        insights.append(f"I found {sum(e[1] for e in emotions)} emotional moments across your videos:")
                        for emotion, count in emotions:
                            insights.append(f"  • {emotion}: {count} instances")
                
                # Search scenes
                if 'scene' in query or 'moment' in query:
                    cursor.execute("""
                        SELECT COUNT(*) FROM scenes 
                        LIMIT 10
                    """)
                    scene_count = cursor.fetchone()[0]
                    insights.append(f"I've identified {scene_count} distinct scenes in your videos")
                
            finally:
                conn.close()
        
        # Get data from knowledge graph
        if KG_DB.exists():
            conn = sqlite3.connect(str(KG_DB))
            cursor = conn.cursor()
            
            try:
                cursor.execute("SELECT COUNT(*) FROM nodes")
                stats['entities'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM edges")
                stats['relationships'] = cursor.fetchone()[0]
                
                # Search for people/entities
                if any(word in query for word in ['who', 'person', 'people', 'entity']):
                    cursor.execute("""
                        SELECT type, COUNT(*) as count 
                        FROM nodes 
                        GROUP BY type 
                        ORDER BY count DESC LIMIT 5
                    """)
                    entities = cursor.fetchall()
                    if entities:
                        insights.append("Entities in your knowledge graph:")
                        for ent_type, count in entities:
                            insights.append(f"  • {ent_type}: {count}")
                
            finally:
                conn.close()
        
        # Build response
        if insights:
            response_text = "\n".join(insights)
        else:
            response_text = f"I found {stats.get('scenes', 0)} scenes, {stats.get('entities', 0)} entities, and {stats.get('embeddings', 0)} embedded moments in your collection."
        
        response = {
            "message": response_text,
            "context": {
                **stats,
                "timestamp": datetime.now().isoformat()
            },
            "suggestions": [
                "Show me emotional moments",
                "What entities do you know about?",
                "Tell me about the scenes",
                "Search for specific content"
            ]
        }
        
        return response
    except Exception as e:
        print(f"Chat error: {e}")
        return {
            "message": f"I'm processing your query: '{message.message}'. The system has data available but I encountered an issue: {str(e)}",
            "context": {"error": str(e)},
            "suggestions": ["Try asking about scenes", "Ask about emotional content"]
        }


@app.post("/api/command")
async def execute_command(request: CommandRequest):
    """Execute system commands"""
    try:
        if request.command == "get_video_list":
            return await list_videos()
        elif request.command == "get_status":
            return await get_status()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown command: {request.command}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/{log_type}")
async def get_logs(log_type: str, lines: int = 100):
    """Get log files"""
    try:
        log_files = {
            "watchdog": "watchdog.log",
            "ingestion": "ingestion.log",
            "visual": "Visual Biometrics.log",
            "audio": "Audio Frequency.log"
        }
        
        if log_type not in log_files:
            raise HTTPException(status_code=404, detail="Log type not found")
        
        log_file = LOGS_DIR / log_files[log_type]
        if not log_file.exists():
            return {"lines": [], "file": log_files[log_type]}
        
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
        
        return {
            "lines": [line.strip() for line in recent_lines],
            "file": log_files[log_type],
            "total_lines": len(all_lines)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/command-center")
async def get_command_center():
    """Get comprehensive command center dashboard data - live system monitoring"""
    try:
        # Get watchdog log for processing status
        watchdog_log = LOGS_DIR / "watchdog.log"
        log_lines = []
        processing_info = {
            "active": False,
            "current_file": None,
            "started": None,
            "progress": "No active processing"
        }
        
        if watchdog_log.exists():
            with open(watchdog_log, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                log_lines = [line.strip() for line in lines[-50:]]  # Last 50 lines
                
                # Parse for current processing
                for line in reversed(lines[-100:]):
                    if "Processing video:" in line:
                        processing_info["active"] = True
                        parts = line.split("Processing video:")
                        if len(parts) > 1:
                            processing_info["current_file"] = parts[1].strip()
                        timestamp_str = line.split('[INFO]')[0].strip()
                        processing_info["started"] = timestamp_str
                        processing_info["progress"] = f"Processing {processing_info['current_file']}"
                        break
                    elif "Successfully processed:" in line:
                        processing_info["active"] = False
                        processing_info["progress"] = "Last job completed successfully"
                        break
                    elif "Failed to process:" in line:
                        processing_info["active"] = False
                        processing_info["progress"] = "Last job failed - check logs"
                        break
        
        # Get database stats
        db_stats = {}
        if MEMORY_DB.exists():
            conn = sqlite3.connect(str(MEMORY_DB))
            cursor = conn.cursor()
            try:
                db_stats["scenes"] = cursor.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
                db_stats["segments"] = cursor.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
                db_stats["embeddings"] = cursor.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
                
                # Get entities if table exists
                try:
                    db_stats["entities"] = cursor.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                except:
                    db_stats["entities"] = 0
                
                # Get relationships if table exists
                try:
                    db_stats["relationships"] = cursor.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
                except:
                    db_stats["relationships"] = 0
                    
                # Get recent activity
                try:
                    cursor.execute("SELECT created_at FROM scenes ORDER BY created_at DESC LIMIT 1")
                    latest = cursor.fetchone()
                    db_stats["latest_activity"] = latest[0] if latest else "No data yet"
                except:
                    db_stats["latest_activity"] = "Unknown"
                    
            finally:
                conn.close()
        
        # Check output directory
        video_count = 0
        total_scenes = 0
        if OUTPUT_DIR.exists():
            video_dirs = [d for d in OUTPUT_DIR.iterdir() if d.is_dir()]
            video_count = len(video_dirs)
            for video_dir in video_dirs:
                scenes_dir = video_dir / "scenes"
                if scenes_dir.exists():
                    total_scenes += len([d for d in scenes_dir.iterdir() if d.is_dir()])
        
        # System health checks
        health = {
            "memory_db": MEMORY_DB.exists(),
            "kg_db": KG_DB.exists(),
            "output_dir": OUTPUT_DIR.exists(),
            "logs_dir": LOGS_DIR.exists(),
            "processing_dir": PROCESSING_DIR.exists(),
        }
        
        # LLM status
        llm_status = {
            "available": llm.available if hasattr(llm, 'available') else False,
            "model": llm.model if hasattr(llm, 'model') and llm.model else "Not configured",
        }
        
        return {
            "status": "active" if processing_info["active"] else "ready",
            "timestamp": datetime.now().isoformat(),
            "processing": processing_info,
            "database": db_stats,
            "system": {
                "videos_processed": video_count,
                "total_scenes": total_scenes,
                "health": health,
                "llm": llm_status
            },
            "logs": {
                "recent": log_lines[-10:],  # Last 10 log lines
                "full_available": len(log_lines)
            }
        }
    except Exception as e:
        print(f"Command center error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes")
async def get_processes():
    """Get status of all managed processes"""
    try:
        # Import process manager
        sys.path.insert(0, str(BASE_DIR))
        from process_manager import create_goodq_manager
        
        manager = create_goodq_manager()
        status = manager.status()
        
        return {
            "processes": status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Process status error: {e}")
        import traceback
        traceback.print_exc()
        # Return minimal info if manager unavailable
        return {
            "processes": {},
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/processes/{process_name}/start")
async def start_process(process_name: str):
    """Start a process"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from process_manager import create_goodq_manager
        
        manager = create_goodq_manager()
        success = manager.start(process_name)
        
        if success:
            return {"status": "started", "process": process_name}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start {process_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/processes/{process_name}/stop")
async def stop_process(process_name: str):
    """Stop a process"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from process_manager import create_goodq_manager
        
        manager = create_goodq_manager()
        success = manager.stop(process_name)
        
        if success:
            return {"status": "stopped", "process": process_name}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to stop {process_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/processes/{process_name}/restart")
async def restart_process(process_name: str):
    """Restart a process"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from process_manager import create_goodq_manager
        
        manager = create_goodq_manager()
        success = manager.restart(process_name)
        
        if success:
            return {"status": "restarted", "process": process_name}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to restart {process_name}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/processes/{process_name}/logs")
async def get_process_logs(process_name: str, lines: int = 100):
    """Get logs for a specific process"""
    try:
        sys.path.insert(0, str(BASE_DIR))
        from process_manager import create_goodq_manager
        
        manager = create_goodq_manager()
        log_lines = manager.get_logs(process_name, lines)
        
        return {
            "process": process_name,
            "lines": log_lines,
            "count": len(log_lines)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/status")
async def websocket_status(websocket: WebSocket):
    """WebSocket for real-time status updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Send status updates every 5 seconds
            status = await get_status()
            await websocket.send_json(status)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


# Mount static files
@app.get("/api/videos/{video_id}/scenes/{scene_id}/frames/{filename}")
async def serve_frame(video_id: str, scene_id: str, filename: str):
    """Serve scene frame images"""
    frame_path = OUTPUT_DIR / video_id / "scenes" / scene_id / "frames" / filename
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)


if __name__ == "__main__":
    print("=" * 80)
    print("GoodQ API Server Starting")
    print("=" * 80)
    print(f"Base Directory: {BASE_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Server will be available at: http://localhost:3000")
    print("=" * 80)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=3000,
        log_level="info",
        access_log=True
    )
