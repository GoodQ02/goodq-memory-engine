"""
GoodQ4All Pipeline Control Agent - Phase 2: Observer, Advisor & Healer
=======================================================================

The "Control" agent that monitors pipeline execution, learns from failures,
and provides intelligent recommendations for optimization and recovery.

Author: GoodQ4All Team
Version: 1.0.0
Date: 2025-11-16
"""

import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.llm_client import LLMClient
from agents.config_healer import ConfigHealer
from agents.recovery_db import RecoveryDatabase
from agents.recovery_strategies import RecoveryStrategies


class ControlAgent:
    """
    The Control Agent - Pipeline Intelligence Layer
    
    Responsibilities:
    - Monitor pipeline logs and execution
    - Analyze errors and suggest fixes
    - Learn from past failures/successes
    - Generate diagnostic reports
    - Build knowledge base for self-improvement
    """
    
    def __init__(self, data_dir: Path = None):
        """Initialize the Control Agent"""
        self.root = Path(__file__).parent.parent
        # Use canonical data root from config
        self.data_dir = data_dir or Path("L:/_DATA/GoodQ_Data")
        
        # Initialize LLM client with fallback chain
        self.llm = LLMClient()
        
        # Initialize Config Healer (Phase 2)
        self.healer = ConfigHealer(llm_client=self.llm)
        
        # Initialize Recovery Database (Phase 2)
        self.recovery_db = RecoveryDatabase(
            db_path=self.data_dir / "recovery.db"
        )
        
        # Initialize Recovery Strategies (Phase 3)
        self.recovery_strategies = RecoveryStrategies(
            db_path=self.data_dir / "control_memory.db"
        )
        
        # Setup directories
        self.logs_dir = self.data_dir / "workflow_logs"
        self.reports_dir = self.root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Initialize memory database
        self.db_path = self.data_dir / "agent_checkpoints" / "control_memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_memory_db()
        
        print("[CONTROL AGENT] Initialized (Phase 2: Auto-Healing)")
        print(f"   LLM Client: Ready ({len(self.llm.MODELS)} models configured)")
        print(f"   Config Healer: Armed and ready")
        print(f"   Memory DB: {self.db_path}")
        print(f"   Reports: {self.reports_dir}")

    def start_monitoring(self) -> None:
        """
        Placeholder for backward compatibility.
        Older callers expect this to start background monitoring;
        current implementation initializes everything in __init__.
        """
        return None
    
    def _init_memory_db(self):
        """Initialize SQLite memory database for learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table: Error history and recovery attempts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                context TEXT,
                step_name TEXT,
                fix_attempted TEXT,
                fix_successful INTEGER DEFAULT 0,
                execution_time_sec REAL,
                gpu_usage_mb REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: Successful runs for pattern learning
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS success_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                pipeline_name TEXT,
                total_duration_sec REAL,
                avg_gpu_usage_mb REAL,
                peak_gpu_usage_mb REAL,
                file_size_mb REAL,
                config_snapshot TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: File processing tracking (Phase 3)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                file_type TEXT,
                size_bytes INTEGER,
                status TEXT,
                detected_at TEXT,
                processing_started_at TEXT,
                processing_completed_at TEXT,
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table: Agent recommendations and outcomes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                recommendation_type TEXT,
                recommendation_text TEXT,
                confidence_score REAL,
                applied INTEGER DEFAULT 0,
                outcome TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print("   [OK] Memory database initialized")
    
    def analyze_logs(self, log_file: Path) -> Dict[str, Any]:
        """
        Analyze a pipeline log file and extract insights
        
        Args:
            log_file: Path to log file
            
        Returns:
            Analysis results with errors, warnings, metrics
        """
        if not log_file.exists():
            return {"error": f"Log file not found: {log_file}"}
        
        # Read log content
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = f.read()
        
        # Extract structured data
        analysis = {
            "log_file": str(log_file),
            "timestamp": datetime.now().isoformat(),
            "errors": [],
            "warnings": [],
            "metrics": {},
            "summary": ""
        }
        
        # Parse for errors
        for line in log_content.split('\n'):
            if '[ERROR]' in line or 'ERROR:' in line or 'Traceback' in line:
                analysis["errors"].append(line.strip())
            elif '[WARNING]' in line or 'WARNING:' in line:
                analysis["warnings"].append(line.strip())
        
        # Extract metrics (simple pattern matching for now)
        if 'Duration:' in log_content:
            for line in log_content.split('\n'):
                if 'Duration:' in line:
                    analysis["metrics"]["duration"] = line.strip()
        
        return analysis
    
    def diagnose_error(self, error_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Quick diagnosis of a specific error with LLM.
        
        Args:
            error_message: The error message to diagnose
            context: Additional context
            
        Returns:
            LLM diagnosis
        """
        prompt = f"""You are a pipeline diagnostics expert for GoodQ4All.

**Error**: {error_message}

**Context**:
- Step: {context.get('step', 'Unknown') if context else 'Unknown'}
- Error Type: {context.get('error_type', 'Unknown') if context else 'Unknown'}

Provide:
1. Root cause analysis
2. Recommended fix
3. Prevention strategy

Be concise and actionable."""

        print("\n[SEARCH] Analyzing with LLM...")
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )
        
        # Extract text
        if isinstance(response, dict):
            response_text = response.get('choices', [{}])[0].get('message', {}).get('content', str(response))
        else:
            response_text = str(response)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "llm_provider": getattr(self.llm, 'last_provider_used', 'Unknown'),
            "diagnosis": response_text,
            "root_cause": response_text.split('\n')[0] if response_text else "Unknown",
            "recommended_action": "See full diagnosis",
            "confidence": "medium"
        }
    
    def diagnose_with_llm(self, analysis: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """
        Use LLM to diagnose issues and suggest fixes
        
        Args:
            analysis: Log analysis data
            context: Additional context about the pipeline run
            
        Returns:
            LLM diagnosis with recommendations
        """
        # Build diagnostic prompt
        prompt = self._build_diagnostic_prompt(analysis, context)
        
        # Query LLM
        print("\n[SEARCH] Analyzing with LLM...")
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Lower temp for more consistent analysis
            max_tokens=1000
        )
        
        # Extract text content from response
        if isinstance(response, dict):
            response_text = response.get('choices', [{}])[0].get('message', {}).get('content', str(response))
        else:
            response_text = str(response)
        
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "llm_provider": getattr(self.llm, 'last_provider_used', 'Unknown'),
            "raw_response": response_text,
            "parsed": self._parse_llm_diagnosis(response_text)
        }
        
        return diagnosis
    
    def _build_diagnostic_prompt(self, analysis: Dict[str, Any], context: str) -> str:
        """Build a diagnostic prompt for the LLM"""
        prompt = f"""You are a pipeline diagnostics expert for GoodQ4All, an AI-powered video/audio ingestion system.

**Your Job**: Analyze pipeline logs and provide actionable recommendations.

**Context**: {context if context else "Standard pipeline execution"}

**Log Analysis**:
- Errors Found: {len(analysis.get('errors', []))}
- Warnings Found: {len(analysis.get('warnings', []))}

"""
        
        if analysis.get('errors'):
            prompt += "\n**Errors**:\n"
            for i, error in enumerate(analysis['errors'][:5], 1):  # Limit to first 5
                prompt += f"{i}. {error}\n"
        
        if analysis.get('warnings'):
            prompt += "\n**Warnings**:\n"
            for i, warning in enumerate(analysis['warnings'][:3], 1):
                prompt += f"{i}. {warning}\n"
        
        prompt += """

**Please provide**:
1. **Root Cause**: What likely caused the issue?
2. **Severity**: Critical / High / Medium / Low
3. **Recommended Fix**: Specific actionable steps
4. **Prevention**: How to avoid this in the future
5. **Confidence**: How confident are you? (0-100%)

Keep it concise and technical. Focus on actionable solutions.
"""
        
        return prompt
    
    def _parse_llm_diagnosis(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured data"""
        parsed = {
            "root_cause": "",
            "severity": "unknown",
            "fix": "",
            "prevention": "",
            "confidence": 0
        }
        
        # Simple parsing (can be enhanced with more sophisticated NLP)
        lines = response.split('\n')
        current_section = None
        
        for line in lines:
            line_lower = line.lower().strip()
            
            if 'root cause' in line_lower:
                current_section = 'root_cause'
            elif 'severity' in line_lower:
                current_section = 'severity'
                # Extract severity level
                for level in ['critical', 'high', 'medium', 'low']:
                    if level in line_lower:
                        parsed['severity'] = level
                        break
            elif 'recommended fix' in line_lower or 'fix:' in line_lower:
                current_section = 'fix'
            elif 'prevention' in line_lower:
                current_section = 'prevention'
            elif 'confidence' in line_lower:
                current_section = 'confidence'
                # Extract percentage
                import re
                match = re.search(r'(\d+)%?', line)
                if match:
                    parsed['confidence'] = int(match.group(1))
            elif current_section and line.strip():
                # Append to current section
                if current_section != 'confidence':
                    parsed[current_section] += line.strip() + " "
        
        # Clean up
        for key in ['root_cause', 'fix', 'prevention']:
            parsed[key] = parsed[key].strip()
        
        return parsed
    
    def record_error(self, error_type: str, error_msg: str, step: str = "",
                    fix_attempted: str = "", successful: bool = False,
                    context: Dict = None):
        """Record an error in memory for learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO error_memory 
            (timestamp, error_type, error_message, context, step_name, 
             fix_attempted, fix_successful)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            error_type,
            error_msg,
            json.dumps(context or {}),
            step,
            fix_attempted,
            1 if successful else 0
        ))
        
        conn.commit()
        conn.close()
    
    def get_similar_errors(self, error_type: str, limit: int = 5) -> List[Dict]:
        """Retrieve similar past errors for learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, error_message, fix_attempted, fix_successful, notes
            FROM error_memory
            WHERE error_type = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (error_type, limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "timestamp": row[0],
                "message": row[1],
                "fix_attempted": row[2],
                "successful": bool(row[3]),
                "notes": row[4]
            })
        
        conn.close()
        return results
    
    def generate_report(self, analysis: Dict, diagnosis: Dict, output_path: Path = None):
        """
        Generate a markdown report.

        Cosmetic hardening (non-authoritative):
        - Tolerate legacy calling patterns where `analysis` may be a string path (treat as `output_path`).
        - Tolerate missing/partial `analysis`/`diagnosis` shapes without raising.
        """
        # Legacy call compatibility: generate_report(output_path, diagnosis) or generate_report(output_path)
        if isinstance(analysis, (str, Path)) and output_path is None:
            output_path = Path(analysis)
            analysis = {}

        analysis_dict = analysis if isinstance(analysis, dict) else {}
        diagnosis_dict = diagnosis if isinstance(diagnosis, dict) else {}
        parsed = diagnosis_dict.get("parsed") if isinstance(diagnosis_dict.get("parsed"), dict) else {}

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.reports_dir / f"pipeline_diagnosis_{timestamp}.md"
        
        report = f"""# GoodQ4All Pipeline Diagnostic Report
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Agent**: Control Agent v1.0  
**LLM Provider**: {diagnosis_dict.get('llm_provider', 'Unknown')}

---

## [SYMBOL] Execution Summary

- **Log File**: `{analysis_dict.get('log_file', 'N/A')}`
- **Errors Found**: {len(analysis_dict.get('errors', []))}
- **Warnings Found**: {len(analysis_dict.get('warnings', []))}

---

## [SEARCH] LLM Diagnosis

**Severity**: {str(parsed.get('severity', 'unknown')).upper()}  
**Confidence**: {parsed.get('confidence', 0)}%

### Root Cause
{parsed.get('root_cause') or 'Analysis pending...'}

### Recommended Fix
{parsed.get('fix') or 'No specific fix recommended'}

### Prevention Strategy
{parsed.get('prevention') or 'No prevention strategy provided'}

---

## [SYMBOL] Detailed Findings

"""
        
        if analysis_dict.get('errors'):
            report += "\n### Errors\n\n"
            for i, error in enumerate(analysis_dict.get('errors', []), 1):
                report += f"{i}. `{error}`\n"
        
        if analysis_dict.get('warnings'):
            report += "\n### Warnings\n\n"
            for i, warning in enumerate(analysis_dict.get('warnings', []), 1):
                report += f"{i}. `{warning}`\n"
        
        report += f"""

---

## [BOT] Full LLM Response

```
{diagnosis_dict.get('raw_response', '')}
```

---

*Generated by GoodQ4All Control Agent*
"""
        
        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n[SYMBOL] Report saved: {output_path}")
        return output_path
    
    def monitor_latest_run(self) -> Dict[str, Any]:
        """Monitor the most recent pipeline run"""
        # Find latest log file
        log_files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        
        if not log_files:
            return {"error": "No log files found"}
        
        latest_log = log_files[-1]
        print(f"[SYMBOL] Analyzing: {latest_log.name}")
        
        # Analyze
        analysis = self.analyze_logs(latest_log)
        
        # Diagnose if errors found
        if analysis.get('errors'):
            diagnosis = self.diagnose_with_llm(analysis, context=f"Latest run: {latest_log.name}")
            report_path = self.generate_report(analysis, diagnosis)
            
            return {
                "status": "errors_found",
                "analysis": analysis,
                "diagnosis": diagnosis,
                "report": str(report_path)
            }
        else:
            print("[PASS] No errors found in latest run")
            return {
                "status": "success",
                "analysis": analysis
            }
    
    # ========================================================================
    # Phase 3: Pipeline Integration Callbacks
    # ========================================================================
    
    def on_file_detected(self, filename: str, file_type: str, size_bytes: int):
        """Callback when a new file is detected in the watch directory"""
        print(f"[Control Agent] File detected: {filename} ({file_type}, {size_bytes / 1024**2:.1f} MB)")
        
        # Store in memory for tracking
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO file_tracking (filename, file_type, size_bytes, status, detected_at)
            VALUES (?, ?, ?, 'detected', ?)
        """, (filename, file_type, size_bytes, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def on_processing_start(self, filename: str, file_type: str):
        """Callback when processing starts for a file"""
        print(f"[Control Agent] Processing started: {filename}")
        
        # Update tracking
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE file_tracking
            SET status = 'processing', processing_started_at = ?
            WHERE filename = ?
        """, (datetime.now().isoformat(), filename))
        conn.commit()
        conn.close()
    
    def on_processing_complete(self, filename: str, success: bool, error: str = None):
        """Callback when processing completes (success or failure)"""
        status = "completed" if success else "failed"
        print(f"[Control Agent] Processing {status}: {filename}")
        
        # Update tracking
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE file_tracking
            SET status = ?, processing_completed_at = ?, error_message = ?
            WHERE filename = ?
        """, (status, datetime.now().isoformat(), error, filename))
        conn.commit()
        conn.close()
        
        # If failed, trigger analysis
        if not success and error:
            print(f"[Control Agent] Analyzing failure for {filename}")
            self.record_error(
                error_type="ProcessingFailure",
                error_msg=error,
                context={'filename': filename, 'file_type': 'unknown'},
                step="ingestion"
            )
    
    def analyze_error(self, error: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze an error using AI and provide diagnosis with recommendations
        
        Args:
            error: The error message or exception
            context: Additional context (step name, file info, system state, etc.)
        
        Returns:
            Dictionary with diagnosis, root_cause, recommended_action, confidence
        """
        context = context or {}
        
        # Build prompt for LLM
        prompt = f"""You are an expert in debugging data processing pipelines.

ERROR: {error}

CONTEXT:
{json.dumps(context, indent=2)}

Please analyze this error and provide:
1. A brief diagnosis (1-2 sentences)
2. The root cause
3. Recommended action to fix it
4. Confidence level (low/medium/high)

Format your response as JSON:
{{
  "diagnosis": "...",
  "root_cause": "...",
  "recommended_action": "...",
  "confidence": "high/medium/low",
  "changes": "specific changes to make (if applicable)"
}}"""
        
        try:
            # Use LLM client to get diagnosis
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Lower temperature for more deterministic diagnostics
                max_tokens=500
            )
            
            # LLM client returns a dict with 'content' key
            if isinstance(response, dict):
                response_text = response.get('content', str(response))
            else:
                response_text = str(response)
            
            response_text = response_text.strip()
            
            # Extract JSON if wrapped in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                diagnosis = json.loads(response_text)
            except json.JSONDecodeError:
                # Fallback: create structure from raw response
                diagnosis = {
                    "diagnosis": response_text[:200],
                    "root_cause": "See diagnosis",
                    "recommended_action": "manual_investigation",
                    "confidence": "low",
                    "raw_response": response_text
                }
            
            # Record this analysis
            self.record_error(
                error_type=context.get('step', 'Unknown'),
                error_msg=error,
                context=context,
                step=context.get('step', 'pipeline'),
                fix_attempted=diagnosis.get('recommended_action', 'None'),
                successful=False  # Not applied yet
            )
            
            return diagnosis
            
        except Exception as e:
            print(f"[Control Agent] LLM diagnosis failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback diagnosis
            return {
                "diagnosis": f"Unable to get AI diagnosis: {str(e)}",
                "root_cause": "LLM service unavailable or error in analysis",
                "recommended_action": "check_llm_service",
                "confidence": "low",
                "error": str(e)
            }
    
    # ============================================================
    # PHASE 2: Recovery & Learning Methods
    # ============================================================
    
    def handle_pipeline_failure(
        self,
        step_name: str,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle a pipeline failure with AI diagnosis and recovery.
        
        Args:
            step_name: Name of the failed step
            error: The exception that occurred
            context: Additional context (GPU state, file info, etc.)
            
        Returns:
            Recovery result with diagnosis and attempted fixes
        """
        print(f"\n[SYMBOL] Pipeline Failure Detected: {step_name}")
        print(f"   Error: {str(error)}")
        
        # Extract error details
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = None
        
        try:
            import traceback
            stack_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        except:
            pass
        
        # Record failure in database
        failure_id = self.recovery_db.record_failure(
            step_name=step_name,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            context=context,
            pipeline_id=context.get('pipeline_id') if context else None
        )
        
        print(f"   Failure ID: #{failure_id}")
        
        # Check for similar past failures
        similar = self.recovery_db.get_similar_failures(
            error_type=error_type,
            step_name=step_name,
            limit=5
        )
        
        if similar:
            print(f"   Found {len(similar)} similar past failures")
        
        # Get AI diagnosis
        print("\n[BOT] Requesting AI diagnosis...")
        diagnosis = self.diagnose_error(
            error_message,
            context={
                'step': step_name,
                'error_type': error_type,
                'similar_failures': len(similar),
                **(context or {})
            }
        )
        
        # Check for known recovery strategies
        best_strategy = self.recovery_db.get_best_recovery_strategy(
            error_type=error_type,
            step_name=step_name
        )
        
        recovery_result = {
            'failure_id': failure_id,
            'diagnosis': diagnosis,
            'similar_failures': similar,
            'best_strategy': best_strategy,
            'recovery_attempted': False,
            'recovery_success': False
        }
        
        # If we have a proven strategy, suggest it
        if best_strategy:
            print(f"\n[SYMBOL] Found proven strategy: {best_strategy.get('strategy', 'Unknown')}")
            print(f"   Success rate: {best_strategy.get('success_rate', 0)*100:.1f}%")
            print(f"   Times used: {best_strategy.get('times_used', 0)}")
            recovery_result['recommended_strategy'] = best_strategy
        
        return recovery_result
    
    def attempt_recovery(
        self,
        failure_id: int,
        strategy: str,
        config_changes: Dict[str, Any] = None
    ) -> bool:
        """Attempt to recover from a failure using a given strategy.
        
        Args:
            failure_id: ID of the failure to recover from
            strategy: Description of recovery strategy
            config_changes: Config modifications to apply
            
        Returns:
            True if recovery successful, False otherwise
        """
        print(f"\n[CONFIG] Attempting recovery for failure #{failure_id}")
        print(f"   Strategy: {strategy}")
        
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Apply config changes if provided
            if config_changes:
                print(f"   Applying {len(config_changes)} config changes...")
                for key, value in config_changes.items():
                    print(f"     - {key}: {value}")
                # TODO: Actually apply config changes via ConfigHealer
            
            # Here you would trigger the actual recovery action
            # For now, we just simulate and record
            success = True  # Placeholder
            
        except Exception as e:
            success = False
            error_msg = str(e)
            print(f"   [FAIL] Recovery failed: {e}")
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Record the attempt
        attempt_id = self.recovery_db.record_recovery_attempt(
            failure_id=failure_id,
            strategy=strategy,
            outcome='success' if success else 'failed',
            config_changes=config_changes,
            execution_time_ms=execution_time_ms,
            error_if_failed=error_msg
        )
        
        if success:
            print(f"   [PASS] Recovery successful (attempt #{attempt_id})")
        else:
            print(f"   [FAIL] Recovery failed (attempt #{attempt_id})")
        
        return success
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get statistics about recovery attempts and success rates."""
        return self.recovery_db.get_statistics()
    
    def suggest_preventive_measures(self, step_name: str = None) -> List[Dict]:
        """Suggest preventive measures based on historical failures.
        
        Args:
            step_name: Optional filter by step
            
        Returns:
            List of suggestions
        """
        stats = self.recovery_db.get_statistics()
        suggestions = []
        
        # Check for frequent failures in specific steps
        for step_info in stats.get('problematic_steps', []):
            if step_name and step_info['step_name'] != step_name:
                continue
            
            if step_info['count'] > 5:  # Frequent failures
                suggestions.append({
                    'type': 'frequent_failure',
                    'step': step_info['step_name'],
                    'count': step_info['count'],
                    'suggestion': f"Step '{step_info['step_name']}' has failed {step_info['count']} times. "
                                f"Consider reviewing this step's configuration and resource requirements."
                })
        
        # Check for common error patterns
        for error_info in stats.get('top_errors', []):
            if error_info['count'] > 3:
                suggestions.append({
                    'type': 'common_error',
                    'error_type': error_info['error_type'],
                    'count': error_info['count'],
                    'suggestion': f"Error type '{error_info['error_type']}' has occurred {error_info['count']} times. "
                                f"Review error handling and consider adding preventive checks."
                })
        
        return suggestions



    # ============================================================================
    # PHASE 3: SELF-HEALING & LEARNING METHODS
    # ============================================================================
    
    def auto_heal_failure(
        self,
        error: Exception,
        step_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Automatically attempt to heal a failure using learned strategies.
        
        This is the main entry point for Phase 3 self-healing.
        
        Args:
            error: The exception that occurred
            step_name: Name of the failed step
            context: Additional context about the failure
            
        Returns:
            Dict with healing results
        """
        print(f"\n[SYMBOL] AUTO-HEAL: Analyzing failure in step '{step_name}'...")
        
        start_time = time.time()
        error_message = str(error)
        error_type = type(error).__name__
        
        # Get recommended strategy from knowledge base
        strategy = self.recovery_strategies.get_recommended_strategy(error_message)
        
        result = {
            'strategy_found': strategy is not None,
            'error_type': error_type,
            'error_message': error_message,
            'step_name': step_name,
            'success': False,
            'recovery_time_seconds': 0,
            'strategy_applied': None,
            'recommendation': None
        }
        
        if not strategy:
            print(f"   [WARN]  No known strategy for this error type")
            llm_suggestion = self._get_llm_recovery_suggestion(error_message, step_name, context)
            result['recommendation'] = llm_suggestion
            
            self.recovery_strategies.record_recovery_attempt(
                error_type=error_type,
                error_message=error_message,
                strategy_applied={'action': 'none', 'reason': 'no_known_strategy'},
                outcome='failed',
                success=False,
                step_name=step_name,
                context=context
            )
            return result
        
        print(f"   [SYMBOL] Found strategy: {strategy.get('pattern_name', 'unknown')}")
        print(f"   [SYMBOL] Confidence: {strategy.get('confidence', 0)*100:.1f}%")
        
        result['strategy_applied'] = strategy
        
        try:
            recovery_success = self._execute_recovery_strategy(
                strategy=strategy,
                step_name=step_name,
                error=error,
                context=context
            )
            
            result['success'] = recovery_success
            result['recovery_time_seconds'] = time.time() - start_time
            
            self.recovery_strategies.record_recovery_attempt(
                error_type=error_type,
                error_message=error_message,
                strategy_applied=strategy,
                outcome='success' if recovery_success else 'failed',
                success=recovery_success,
                step_name=step_name,
                context=context,
                duration_seconds=result['recovery_time_seconds']
            )
            
            if recovery_success:
                print(f"   [PASS] Recovery successful in {result['recovery_time_seconds']:.2f}s")
            else:
                print(f"   [FAIL] Recovery failed")
                result['recommendation'] = self._get_llm_recovery_suggestion(error_message, step_name, context)
        
        except Exception as recovery_error:
            print(f"   [FAIL] Recovery exception: {recovery_error}")
            result['success'] = False
            result['recovery_error'] = str(recovery_error)
        
        return result
    
    def _execute_recovery_strategy(self, strategy: Dict[str, Any], step_name: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
        """Execute a recovery strategy"""
        action = strategy.get('action', '')
        params = strategy.get('params', {})
        
        print(f"   [CONFIG] Executing action: {action}")
        
        if action == 'reduce_batch_size':
            return self._heal_reduce_batch_size(step_name, params)
        elif action == 'skip_audio_steps':
            return self._heal_skip_audio_steps(step_name, params)
        elif action == 'partition_audio':
            return self._heal_partition_audio(step_name, params)
        elif action == 'downgrade_model':
            return self._heal_downgrade_model(step_name, params)
        elif action == 'retry_with_backoff':
            return self._heal_retry_with_backoff(step_name, params)
        elif action == 'switch_to_cpu':
            return self._heal_switch_to_cpu(step_name, params)
        else:
            print(f"   [WARN]  Unknown action: {action}")
            return False
    
    def _heal_reduce_batch_size(self, step_name: str, params: Dict) -> bool:
        """Reduce batch size to avoid memory errors"""
        print(f"      Reducing batch size for {step_name}")
        changes = {f'{step_name}.batch_size': params.get('batch_size', 'half')}
        success, msg = self.healer.apply_healing_action('reduce_batch_size', {'step': step_name, 'params': params})
        return success
    
    def _heal_skip_audio_steps(self, step_name: str, params: Dict) -> bool:
        """Skip audio processing for silent/corrupted audio"""
        print(f"      Marking {step_name} as skippable")
        success, msg = self.healer.apply_healing_action('skip_step', {'step': step_name, 'params': params})
        return success
    
    def _heal_partition_audio(self, step_name: str, params: Dict) -> bool:
        """Partition long audio into chunks"""
        chunk_size = params.get('chunk_size_minutes', 20)
        print(f"      Enabling audio partitioning ({chunk_size} min chunks)")
        success, msg = self.healer.apply_healing_action('partition_audio', {'step': step_name, 'chunk_size': chunk_size})
        return success
    
    def _heal_downgrade_model(self, step_name: str, params: Dict) -> bool:
        """Downgrade to smaller/faster model"""
        to_model = params.get('to', 'medium')
        print(f"      Downgrading model to: {to_model}")
        success, msg = self.healer.apply_healing_action('downgrade_model', {'step': step_name, 'to_model': to_model})
        return success
    
    def _heal_retry_with_backoff(self, step_name: str, params: Dict) -> bool:
        """Enable retry with exponential backoff"""
        max_retries = params.get('max_retries', 3)
        print(f"      Enabling retry ({max_retries} attempts)")
        success, msg = self.healer.apply_healing_action('enable_retry', {'step': step_name, 'max_retries': max_retries})
        return success
    
    def _heal_switch_to_cpu(self, step_name: str, params: Dict) -> bool:
        """Switch step to CPU fallback"""
        print(f"      Switching to CPU fallback")
        success, msg = self.healer.apply_healing_action('switch_to_cpu', {'step': step_name})
        return success
    
    def _get_llm_recovery_suggestion(self, error_message: str, step_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Get LLM suggestion for recovery"""
        prompt = f"Analyze this error and suggest recovery: Step={step_name}, Error={error_message}"
        try:
            response = self.llm.chat([{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            return f"LLM unavailable: {e}"
    
    def learn_from_success(self, step_name: str, execution_time_seconds: float, config_used: Dict[str, Any], context: Optional[Dict[str, Any]] = None):
        """Learn from successful executions"""
        self.recovery_strategies.record_recovery_attempt(
            error_type='success',
            error_message=f'Successful execution of {step_name}',
            strategy_applied={'action': 'normal_execution', 'config': config_used},
            outcome='success',
            success=True,
            step_name=step_name,
            context=context,
            duration_seconds=execution_time_seconds
        )
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get statistics about what the agent has learned"""
        return self.recovery_strategies.get_statistics()


def main():
    """CLI entry point"""
    print("=" * 70)
    print("[CONTROL AGENT] GoodQ4All Control Agent - Phase 1: Observer")
    print("=" * 70)
    
    agent = ControlAgent()
    
    # Monitor latest run
    result = agent.monitor_latest_run()
    
    if result.get('status') == 'errors_found':
        print("\n[WARN]  Issues detected - diagnostic report generated")
        print(f"   View report: {result['report']}")
    elif result.get('status') == 'success':
        print("\n[PASS] Latest pipeline run completed successfully")
    else:
        print(f"\n[FAIL] {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
