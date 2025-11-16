"""
Recovery Strategies Database for Control Agent Self-Healing

This module maintains a knowledge base of error patterns and recovery strategies
that the Control Agent learns over time.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class RecoveryStrategies:
    """Maintains a database of error patterns and successful recovery strategies"""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "control_memory.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize the recovery strategies database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recovery_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    step_name TEXT,
                    context TEXT,
                    strategy_applied TEXT,
                    outcome TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    duration_seconds REAL,
                    gpu_usage_mb INTEGER,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT UNIQUE NOT NULL,
                    error_regex TEXT NOT NULL,
                    recommended_strategy TEXT NOT NULL,
                    success_rate REAL DEFAULT 0.0,
                    total_attempts INTEGER DEFAULT 0,
                    successful_attempts INTEGER DEFAULT 0,
                    last_updated TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_error_type 
                ON recovery_history(error_type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_step_name 
                ON recovery_history(step_name)
            """)
            
            # Seed with known patterns
            self._seed_initial_patterns(conn)
    
    def _seed_initial_patterns(self, conn):
        """Seed database with known error patterns from documentation"""
        patterns = [
            {
                "pattern_name": "cuda_oom",
                "error_regex": r"(?i)(CUDA|GPU).*out of memory|RuntimeError.*memory",
                "recommended_strategy": json.dumps({
                    "action": "reduce_batch_size",
                    "params": {"batch_size": "half"},
                    "fallback": "switch_to_cpu"
                })
            },
            {
                "pattern_name": "no_audio_stream",
                "error_regex": r"(?i)no audio stream|ValueError.*audio",
                "recommended_strategy": json.dumps({
                    "action": "skip_audio_steps",
                    "params": {"mark_as_silent": True}
                })
            },
            {
                "pattern_name": "diarization_timeout",
                "error_regex": r"(?i)pyannote.*timeout|diarization.*failed",
                "recommended_strategy": json.dumps({
                    "action": "partition_audio",
                    "params": {"chunk_size_minutes": 20}
                })
            },
            {
                "pattern_name": "whisper_failure",
                "error_regex": r"(?i)whisper.*failed|transcription.*error",
                "recommended_strategy": json.dumps({
                    "action": "downgrade_model",
                    "params": {"from": "large", "to": "medium"},
                    "fallback": {"from": "medium", "to": "base"}
                })
            },
            {
                "pattern_name": "connection_timeout",
                "error_regex": r"(?i)connection.*timeout|timed out",
                "recommended_strategy": json.dumps({
                    "action": "retry_with_backoff",
                    "params": {"max_retries": 3, "backoff_seconds": [5, 15, 30]}
                })
            }
        ]
        
        for pattern in patterns:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO error_patterns 
                    (pattern_name, error_regex, recommended_strategy, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (
                    pattern["pattern_name"],
                    pattern["error_regex"],
                    pattern["recommended_strategy"],
                    datetime.now().isoformat()
                ))
            except sqlite3.IntegrityError:
                pass  # Pattern already exists
    
    def record_recovery_attempt(
        self,
        error_type: str,
        error_message: str,
        strategy_applied: Dict[str, Any],
        outcome: str,
        success: bool,
        step_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        duration_seconds: Optional[float] = None,
        gpu_usage_mb: Optional[int] = None
    ) -> int:
        """Record a recovery attempt and its outcome"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO recovery_history 
                (timestamp, error_type, error_message, step_name, context, 
                 strategy_applied, outcome, success, duration_seconds, gpu_usage_mb, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                error_type,
                error_message[:500],  # Truncate long messages
                step_name,
                json.dumps(context) if context else None,
                json.dumps(strategy_applied),
                outcome,
                success,
                duration_seconds,
                gpu_usage_mb,
                None
            ))
            
            record_id = cursor.lastrowid
            
            # Update pattern success rate if matched
            self._update_pattern_stats(conn, error_type, error_message, success)
            
            return record_id
    
    def _update_pattern_stats(self, conn, error_type: str, error_message: str, success: bool):
        """Update success rate for matched error patterns"""
        import re
        
        cursor = conn.execute("SELECT id, pattern_name, error_regex FROM error_patterns")
        for row in cursor.fetchall():
            pattern_id, pattern_name, error_regex = row
            
            try:
                if re.search(error_regex, error_message, re.IGNORECASE):
                    conn.execute("""
                        UPDATE error_patterns 
                        SET total_attempts = total_attempts + 1,
                            successful_attempts = successful_attempts + ?,
                            success_rate = CAST(successful_attempts AS REAL) / total_attempts,
                            last_updated = ?
                        WHERE id = ?
                    """, (1 if success else 0, datetime.now().isoformat(), pattern_id))
                    break
            except re.error:
                logger.warning(f"Invalid regex pattern: {error_regex}")
    
    def get_recommended_strategy(self, error_message: str) -> Optional[Dict[str, Any]]:
        """Get recommended recovery strategy for an error"""
        import re
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT pattern_name, recommended_strategy, success_rate 
                FROM error_patterns 
                ORDER BY success_rate DESC
            """)
            
            for row in cursor.fetchall():
                pattern_name, strategy_json, success_rate = row
                
                # Get pattern regex
                regex_cursor = conn.execute(
                    "SELECT error_regex FROM error_patterns WHERE pattern_name = ?",
                    (pattern_name,)
                )
                error_regex = regex_cursor.fetchone()[0]
                
                try:
                    if re.search(error_regex, error_message, re.IGNORECASE):
                        strategy = json.loads(strategy_json)
                        strategy['confidence'] = success_rate if success_rate else 0.5
                        strategy['pattern_name'] = pattern_name
                        return strategy
                except (re.error, json.JSONDecodeError) as e:
                    logger.warning(f"Error processing pattern {pattern_name}: {e}")
        
        return None
    
    def get_similar_past_errors(
        self,
        error_type: str,
        limit: int = 5,
        success_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Retrieve similar past errors and their solutions"""
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT timestamp, error_message, strategy_applied, outcome, 
                       success, duration_seconds
                FROM recovery_history 
                WHERE error_type = ?
            """
            
            if success_only:
                query += " AND success = 1"
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            
            cursor = conn.execute(query, (error_type, limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'timestamp': row[0],
                    'error_message': row[1],
                    'strategy_applied': json.loads(row[2]),
                    'outcome': row[3],
                    'success': bool(row[4]),
                    'duration_seconds': row[5]
                })
            
            return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall recovery statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Total attempts
            total = conn.execute(
                "SELECT COUNT(*) FROM recovery_history"
            ).fetchone()[0]
            
            # Success rate
            success = conn.execute(
                "SELECT COUNT(*) FROM recovery_history WHERE success = 1"
            ).fetchone()[0]
            
            # By error type
            by_type = {}
            cursor = conn.execute("""
                SELECT error_type, 
                       COUNT(*) as total,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM recovery_history 
                GROUP BY error_type
            """)
            
            for row in cursor.fetchall():
                error_type, type_total, type_success = row
                by_type[error_type] = {
                    'total': type_total,
                    'successful': type_success,
                    'success_rate': type_success / type_total if type_total > 0 else 0
                }
            
            # Top patterns
            top_patterns = []
            cursor = conn.execute("""
                SELECT pattern_name, success_rate, total_attempts 
                FROM error_patterns 
                WHERE total_attempts > 0
                ORDER BY success_rate DESC, total_attempts DESC 
                LIMIT 10
            """)
            
            for row in cursor.fetchall():
                top_patterns.append({
                    'pattern': row[0],
                    'success_rate': row[1],
                    'attempts': row[2]
                })
            
            return {
                'total_attempts': total,
                'successful_attempts': success,
                'overall_success_rate': success / total if total > 0 else 0,
                'by_error_type': by_type,
                'top_patterns': top_patterns
            }
    
    def learn_new_pattern(
        self,
        pattern_name: str,
        error_regex: str,
        recommended_strategy: Dict[str, Any]
    ):
        """Learn a new error pattern from experience"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO error_patterns 
                    (pattern_name, error_regex, recommended_strategy, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (
                    pattern_name,
                    error_regex,
                    json.dumps(recommended_strategy),
                    datetime.now().isoformat()
                ))
                logger.info(f"Learned new pattern: {pattern_name}")
            except sqlite3.IntegrityError:
                # Pattern exists, update it
                conn.execute("""
                    UPDATE error_patterns 
                    SET recommended_strategy = ?,
                        last_updated = ?
                    WHERE pattern_name = ?
                """, (
                    json.dumps(recommended_strategy),
                    datetime.now().isoformat(),
                    pattern_name
                ))
                logger.info(f"Updated existing pattern: {pattern_name}")
