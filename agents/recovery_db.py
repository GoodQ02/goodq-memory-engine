"""
GoodQ4All Recovery Database - Phase 2
Tracks pipeline failures, recovery attempts, and outcomes for learning.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class RecoveryDatabase:
    """Persistent storage for pipeline recovery knowledge."""
    
    def __init__(self, db_path: str = None):
        """Initialize recovery database.
        
        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "recovery.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._init_schema()
        
        logger.info(f"Recovery database initialized: {self.db_path}")
    
    def _init_schema(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Failures table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pipeline_id TEXT,
                step_name TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                stack_trace TEXT,
                context TEXT,  -- JSON: GPU state, file size, etc.
                severity TEXT DEFAULT 'ERROR',
                resolved BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Recovery attempts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recovery_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                failure_id INTEGER NOT NULL,
                strategy TEXT NOT NULL,  -- What we tried
                config_changes TEXT,     -- JSON: What we changed
                outcome TEXT NOT NULL,   -- 'success', 'partial', 'failed'
                execution_time_ms INTEGER,
                gpu_usage_mb INTEGER,
                error_if_failed TEXT,
                ai_diagnosis TEXT,       -- LLM's analysis
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (failure_id) REFERENCES failures(id)
            )
        """)
        
        # Success patterns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS success_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_pattern TEXT NOT NULL,  -- Regex or keywords
                recovery_strategy TEXT NOT NULL,
                success_rate REAL DEFAULT 0.0,
                times_used INTEGER DEFAULT 0,
                times_succeeded INTEGER DEFAULT 0,
                avg_execution_time_ms INTEGER,
                config_template TEXT,  -- JSON: Recommended config changes
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used TEXT
            )
        """)
        
        # System metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                gpu_utilization REAL,
                gpu_memory_used_mb INTEGER,
                gpu_memory_total_mb INTEGER,
                cpu_percent REAL,
                ram_used_mb INTEGER,
                active_models TEXT,  -- JSON: List of models loaded
                pipeline_state TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_step 
            ON failures(step_name)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_failures_type 
            ON failures(error_type)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recovery_outcome 
            ON recovery_attempts(outcome)
        """)
        
        self.conn.commit()
    
    def record_failure(
        self,
        step_name: str,
        error_type: str,
        error_message: str,
        stack_trace: str = None,
        context: Dict[str, Any] = None,
        pipeline_id: str = None,
        severity: str = "ERROR"
    ) -> int:
        """Record a pipeline failure.
        
        Args:
            step_name: Name of the pipeline step that failed
            error_type: Type of error (e.g., 'RuntimeError', 'CUDA OOM')
            error_message: Error message
            stack_trace: Full stack trace
            context: Additional context (GPU state, file info, etc.)
            pipeline_id: ID of the pipeline run
            severity: ERROR, WARNING, CRITICAL
            
        Returns:
            Failure ID
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO failures (
                timestamp, pipeline_id, step_name, error_type,
                error_message, stack_trace, context, severity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            pipeline_id,
            step_name,
            error_type,
            error_message,
            stack_trace,
            json.dumps(context) if context else None,
            severity
        ))
        
        self.conn.commit()
        failure_id = cursor.lastrowid
        
        logger.info(f"Recorded failure #{failure_id}: {step_name} - {error_type}")
        return failure_id
    
    def record_recovery_attempt(
        self,
        failure_id: int,
        strategy: str,
        outcome: str,
        config_changes: Dict[str, Any] = None,
        execution_time_ms: int = None,
        gpu_usage_mb: int = None,
        error_if_failed: str = None,
        ai_diagnosis: str = None
    ) -> int:
        """Record a recovery attempt.
        
        Args:
            failure_id: ID of the failure being addressed
            strategy: Description of recovery strategy
            outcome: 'success', 'partial', 'failed'
            config_changes: Config modifications made
            execution_time_ms: How long the recovery took
            gpu_usage_mb: GPU memory used
            error_if_failed: Error message if recovery failed
            ai_diagnosis: LLM's analysis of the situation
            
        Returns:
            Recovery attempt ID
        """
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO recovery_attempts (
                failure_id, strategy, config_changes, outcome,
                execution_time_ms, gpu_usage_mb, error_if_failed,
                ai_diagnosis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            failure_id,
            strategy,
            json.dumps(config_changes) if config_changes else None,
            outcome,
            execution_time_ms,
            gpu_usage_mb,
            error_if_failed,
            ai_diagnosis
        ))
        
        self.conn.commit()
        attempt_id = cursor.lastrowid
        
        # Update success patterns if successful
        if outcome == 'success':
            self._update_success_pattern(strategy, config_changes, execution_time_ms)
            self._mark_failure_resolved(failure_id)
        
        logger.info(f"Recorded recovery attempt #{attempt_id}: {strategy} -> {outcome}")
        return attempt_id
    
    def _update_success_pattern(
        self,
        strategy: str,
        config_changes: Dict[str, Any],
        execution_time_ms: int
    ):
        """Update or create success pattern entry."""
        cursor = self.conn.cursor()
        
        # Check if pattern exists
        cursor.execute("""
            SELECT id, times_used, times_succeeded, avg_execution_time_ms
            FROM success_patterns
            WHERE recovery_strategy = ?
        """, (strategy,))
        
        row = cursor.fetchone()
        
        if row:
            # Update existing pattern
            pattern_id = row['id']
            times_used = row['times_used'] + 1
            times_succeeded = row['times_succeeded'] + 1
            
            # Update average execution time
            if execution_time_ms:
                old_avg = row['avg_execution_time_ms'] or 0
                new_avg = int((old_avg * (times_used - 1) + execution_time_ms) / times_used)
            else:
                new_avg = row['avg_execution_time_ms']
            
            success_rate = times_succeeded / times_used
            
            cursor.execute("""
                UPDATE success_patterns
                SET times_used = ?,
                    times_succeeded = ?,
                    success_rate = ?,
                    avg_execution_time_ms = ?,
                    last_used = ?
                WHERE id = ?
            """, (times_used, times_succeeded, success_rate, new_avg, 
                  datetime.now().isoformat(), pattern_id))
        else:
            # Create new pattern
            cursor.execute("""
                INSERT INTO success_patterns (
                    error_pattern, recovery_strategy, success_rate,
                    times_used, times_succeeded, avg_execution_time_ms,
                    config_template, last_used
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                strategy,  # Will refine error pattern matching later
                strategy,
                1.0,
                1,
                1,
                execution_time_ms,
                json.dumps(config_changes) if config_changes else None,
                datetime.now().isoformat()
            ))
        
        self.conn.commit()
    
    def _mark_failure_resolved(self, failure_id: int):
        """Mark a failure as resolved."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE failures SET resolved = 1 WHERE id = ?
        """, (failure_id,))
        self.conn.commit()
    
    def get_similar_failures(
        self,
        error_type: str = None,
        step_name: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """Find similar past failures.
        
        Args:
            error_type: Filter by error type
            step_name: Filter by step name
            limit: Maximum results
            
        Returns:
            List of failure records with recovery attempts
        """
        cursor = self.conn.cursor()
        
        query = """
            SELECT f.*, 
                   COUNT(r.id) as recovery_attempts,
                   MAX(CASE WHEN r.outcome = 'success' THEN 1 ELSE 0 END) as was_resolved
            FROM failures f
            LEFT JOIN recovery_attempts r ON f.id = r.failure_id
            WHERE 1=1
        """
        params = []
        
        if error_type:
            query += " AND f.error_type = ?"
            params.append(error_type)
        
        if step_name:
            query += " AND f.step_name = ?"
            params.append(step_name)
        
        query += """
            GROUP BY f.id
            ORDER BY f.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_best_recovery_strategy(
        self,
        error_type: str = None,
        step_name: str = None
    ) -> Optional[Dict]:
        """Get the most successful recovery strategy for a given error.
        
        Args:
            error_type: Type of error
            step_name: Pipeline step
            
        Returns:
            Best strategy or None
        """
        # First, try to find exact match in success patterns
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT *
            FROM success_patterns
            WHERE success_rate > 0.5
            ORDER BY success_rate DESC, times_used DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        if row:
            return dict(row)
        
        # Fallback: Find successful recovery attempts
        query = """
            SELECT r.strategy, r.config_changes, r.ai_diagnosis,
                   COUNT(*) as times_used,
                   AVG(r.execution_time_ms) as avg_time
            FROM recovery_attempts r
            JOIN failures f ON r.failure_id = f.id
            WHERE r.outcome = 'success'
        """
        params = []
        
        if error_type:
            query += " AND f.error_type = ?"
            params.append(error_type)
        
        if step_name:
            query += " AND f.step_name = ?"
            params.append(step_name)
        
        query += """
            GROUP BY r.strategy
            ORDER BY COUNT(*) DESC, AVG(r.execution_time_ms) ASC
            LIMIT 1
        """
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        return dict(row) if row else None
    
    def record_system_metrics(
        self,
        gpu_utilization: float = None,
        gpu_memory_used_mb: int = None,
        gpu_memory_total_mb: int = None,
        cpu_percent: float = None,
        ram_used_mb: int = None,
        active_models: List[str] = None,
        pipeline_state: str = None
    ):
        """Record system metrics snapshot."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO system_metrics (
                timestamp, gpu_utilization, gpu_memory_used_mb,
                gpu_memory_total_mb, cpu_percent, ram_used_mb,
                active_models, pipeline_state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            gpu_utilization,
            gpu_memory_used_mb,
            gpu_memory_total_mb,
            cpu_percent,
            ram_used_mb,
            json.dumps(active_models) if active_models else None,
            pipeline_state
        ))
        
        self.conn.commit()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics.
        
        Returns:
            Statistics dictionary
        """
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total failures
        cursor.execute("SELECT COUNT(*) as count FROM failures")
        stats['total_failures'] = cursor.fetchone()['count']
        
        # Resolved failures
        cursor.execute("SELECT COUNT(*) as count FROM failures WHERE resolved = 1")
        stats['resolved_failures'] = cursor.fetchone()['count']
        
        # Resolution rate
        if stats['total_failures'] > 0:
            stats['resolution_rate'] = stats['resolved_failures'] / stats['total_failures']
        else:
            stats['resolution_rate'] = 0.0
        
        # Most common errors
        cursor.execute("""
            SELECT error_type, COUNT(*) as count
            FROM failures
            GROUP BY error_type
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['top_errors'] = [dict(row) for row in cursor.fetchall()]
        
        # Most problematic steps
        cursor.execute("""
            SELECT step_name, COUNT(*) as count
            FROM failures
            GROUP BY step_name
            ORDER BY count DESC
            LIMIT 5
        """)
        stats['problematic_steps'] = [dict(row) for row in cursor.fetchall()]
        
        # Best strategies
        cursor.execute("""
            SELECT recovery_strategy, success_rate, times_used
            FROM success_patterns
            ORDER BY success_rate DESC, times_used DESC
            LIMIT 5
        """)
        stats['best_strategies'] = [dict(row) for row in cursor.fetchall()]
        
        return stats
    
    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("Recovery database closed")


# Convenience function for quick access
_global_db = None

def get_recovery_db() -> RecoveryDatabase:
    """Get global recovery database instance."""
    global _global_db
    if _global_db is None:
        _global_db = RecoveryDatabase()
    return _global_db
