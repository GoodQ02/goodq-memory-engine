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
        self.data_dir = data_dir or self.root / "data"
        
        # Initialize LLM client with fallback chain
        self.llm = LLMClient()
        
        # Initialize Config Healer (Phase 2)
        self.healer = ConfigHealer(llm_client=self.llm)
        
        # Setup directories
        self.logs_dir = self.data_dir / "workflow_logs"
        self.reports_dir = self.root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Initialize memory database
        self.db_path = self.data_dir / "agent_checkpoints" / "control_memory.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_memory_db()
        
        print(f"🧠 Control Agent initialized (Phase 2: Auto-Healing)")
        print(f"   LLM Client: Ready ({len(self.llm.MODELS)} models configured)")
        print(f"   Config Healer: Armed and ready")
        print(f"   Memory DB: {self.db_path}")
        print(f"   Reports: {self.reports_dir}")
    
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
        print("   ✓ Memory database initialized")
    
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
        print("\n🔍 Analyzing with LLM...")
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
        """Generate a markdown report"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = self.reports_dir / f"pipeline_diagnosis_{timestamp}.md"
        
        report = f"""# GoodQ4All Pipeline Diagnostic Report
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**Agent**: Control Agent v1.0  
**LLM Provider**: {diagnosis.get('llm_provider', 'Unknown')}

---

## 📊 Execution Summary

- **Log File**: `{analysis.get('log_file', 'N/A')}`
- **Errors Found**: {len(analysis.get('errors', []))}
- **Warnings Found**: {len(analysis.get('warnings', []))}

---

## 🔍 LLM Diagnosis

**Severity**: {diagnosis['parsed']['severity'].upper()}  
**Confidence**: {diagnosis['parsed']['confidence']}%

### Root Cause
{diagnosis['parsed']['root_cause'] or 'Analysis pending...'}

### Recommended Fix
{diagnosis['parsed']['fix'] or 'No specific fix recommended'}

### Prevention Strategy
{diagnosis['parsed']['prevention'] or 'No prevention strategy provided'}

---

## 📋 Detailed Findings

"""
        
        if analysis.get('errors'):
            report += "\n### Errors\n\n"
            for i, error in enumerate(analysis['errors'], 1):
                report += f"{i}. `{error}`\n"
        
        if analysis.get('warnings'):
            report += "\n### Warnings\n\n"
            for i, warning in enumerate(analysis['warnings'], 1):
                report += f"{i}. `{warning}`\n"
        
        report += f"""

---

## 🤖 Full LLM Response

```
{diagnosis['raw_response']}
```

---

*Generated by GoodQ4All Control Agent*
"""
        
        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📄 Report saved: {output_path}")
        return output_path
    
    def monitor_latest_run(self) -> Dict[str, Any]:
        """Monitor the most recent pipeline run"""
        # Find latest log file
        log_files = sorted(self.logs_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
        
        if not log_files:
            return {"error": "No log files found"}
        
        latest_log = log_files[-1]
        print(f"📂 Analyzing: {latest_log.name}")
        
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
            print("✅ No errors found in latest run")
            return {
                "status": "success",
                "analysis": analysis
            }


def main():
    """CLI entry point"""
    print("=" * 70)
    print("🧠 GoodQ4All Control Agent - Phase 1: Observer")
    print("=" * 70)
    
    agent = ControlAgent()
    
    # Monitor latest run
    result = agent.monitor_latest_run()
    
    if result.get('status') == 'errors_found':
        print("\n⚠️  Issues detected - diagnostic report generated")
        print(f"   View report: {result['report']}")
    elif result.get('status') == 'success':
        print("\n✅ Latest pipeline run completed successfully")
    else:
        print(f"\n❌ {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
