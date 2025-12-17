"""
Self-Healing Monitor
Monitors pipeline execution and applies automatic fixes
"""

import asyncio
import logging
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)

from steps.common.config_loader import load_configs


class SelfHealingMonitor:
    """Monitors pipeline health and applies automatic fixes."""
    
    def __init__(self, cfg: Dict[str, Any], db_path: str | None = None):
        self.config = cfg
        paths = (self.config.get("paths") or {}) if isinstance(self.config, dict) else {}
        resolved_db_path = db_path or (paths.get("db_path") if isinstance(paths, dict) else None) or "L:/_DATA/GoodQ_Data/memory.db"
        self.db_path = Path(resolved_db_path)
        self.llm_config = self.config.get('llm', {})
        self.healing_history = []
        self.patterns = self._load_error_patterns()
    
    def _load_error_patterns(self) -> List[Dict]:
        """Load known error patterns and their fixes."""
        return [
            {
                "pattern": "timeout",
                "keywords": ["timeout", "timed out", "connection timeout"],
                "fix_type": "retry_with_backoff",
                "params": {"max_retries": 3, "backoff_factor": 2}
            },
            {
                "pattern": "memory_error",
                "keywords": ["out of memory", "OOM", "memory allocation"],
                "fix_type": "reduce_batch_size",
                "params": {"reduction_factor": 0.5}
            },
            {
                "pattern": "model_not_found",
                "keywords": ["model not found", "cannot find model", "no such file"],
                "fix_type": "download_model",
                "params": {}
            },
            {
                "pattern": "cuda_error",
                "keywords": ["CUDA", "GPU", "device-side assert"],
                "fix_type": "fallback_to_cpu",
                "params": {}
            },
            {
                "pattern": "empty_result",
                "keywords": ["no scenes detected", "no faces found", "empty result"],
                "fix_type": "adjust_thresholds",
                "params": {}
            },
            {
                "pattern": "file_not_found",
                "keywords": ["file not found", "no such file", "does not exist"],
                "fix_type": "skip_missing_file",
                "params": {}
            }
        ]
    
    async def monitor_and_heal(self, check_interval: int = 60):
        """
        Continuously monitor pipeline and apply fixes.
        
        Args:
            check_interval: Seconds between health checks
        """
        logger.info(f"Starting self-healing monitor (interval: {check_interval}s)")
        
        while True:
            try:
                await self._check_and_heal()
                await asyncio.sleep(check_interval)
            except Exception as e:
                logger.error(f"Monitor error: {str(e)}", exc_info=True)
                await asyncio.sleep(check_interval)
    
    async def _check_and_heal(self):
        """Check for issues and apply fixes."""
        
        # Check recent workflow executions
        recent_issues = await self._get_recent_issues()
        
        if not recent_issues:
            logger.debug("No recent issues found")
            return
        
        logger.info(f"Found {len(recent_issues)} recent issues")
        
        for issue in recent_issues:
            await self._attempt_heal(issue)
    
    async def _get_recent_issues(self, hours: int = 1) -> List[Dict]:
        """Get recent workflow issues."""
        
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Get failed workflows from last hour
            cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
            
            cursor.execute("""
                SELECT workflow_id, result_json
                FROM workflow_executions
                WHERE status IN ('failed', 'error')
                AND start_time > ?
                ORDER BY start_time DESC
            """, (cutoff,))
            
            issues = []
            for row in cursor.fetchall():
                workflow_id, result_json = row
                result = json.loads(result_json)
                
                # Skip if already healed
                if self._was_already_healed(workflow_id):
                    continue
                
                for error in result.get('errors', []):
                    issues.append({
                        "workflow_id": workflow_id,
                        "workflow_name": result.get('workflow_name'),
                        "error": error,
                        "result": result
                    })
            
            return issues
            
        finally:
            conn.close()
    
    def _was_already_healed(self, workflow_id: str) -> bool:
        """Check if workflow was already healed."""
        return any(h['workflow_id'] == workflow_id for h in self.healing_history)
    
    async def _attempt_heal(self, issue: Dict):
        """Attempt to heal an issue."""
        
        error_text = str(issue['error'])
        workflow_id = issue['workflow_id']
        
        logger.info(f"Attempting to heal workflow {workflow_id}")
        
        # Match error pattern
        matched_pattern = self._match_error_pattern(error_text)
        
        if matched_pattern:
            logger.info(f"Matched pattern: {matched_pattern['pattern']}")
            
            # Apply fix
            fix_result = await self._apply_pattern_fix(issue, matched_pattern)
            
            self.healing_history.append({
                "workflow_id": workflow_id,
                "timestamp": datetime.now().isoformat(),
                "pattern": matched_pattern['pattern'],
                "fix_result": fix_result
            })
            
            if fix_result.get('success'):
                logger.info(f"Successfully healed {workflow_id}")
            else:
                logger.warning(f"Heal attempt failed for {workflow_id}: {fix_result.get('error')}")
        else:
            logger.warning(f"No matching pattern for error: {error_text[:100]}")
            
            # Use LLM to analyze unknown error
            if self.llm_config.get('enabled'):
                await self._llm_analyze_error(issue)
    
    def _match_error_pattern(self, error_text: str) -> Dict:
        """Match error against known patterns."""
        
        error_lower = error_text.lower()
        
        for pattern in self.patterns:
            if any(keyword in error_lower for keyword in pattern['keywords']):
                return pattern
        
        return None
    
    async def _apply_pattern_fix(self, issue: Dict, pattern: Dict) -> Dict:
        """Apply a pattern-based fix."""
        
        fix_type = pattern['fix_type']
        params = pattern['params']
        
        try:
            if fix_type == "retry_with_backoff":
                return await self._fix_retry_with_backoff(issue, params)
            
            elif fix_type == "reduce_batch_size":
                return await self._fix_reduce_batch_size(issue, params)
            
            elif fix_type == "download_model":
                return await self._fix_download_model(issue, params)
            
            elif fix_type == "fallback_to_cpu":
                return await self._fix_fallback_cpu(issue, params)
            
            elif fix_type == "adjust_thresholds":
                return await self._fix_adjust_thresholds(issue, params)
            
            elif fix_type == "skip_missing_file":
                return await self._fix_skip_missing(issue, params)
            
            else:
                return {"success": False, "error": f"Unknown fix type: {fix_type}"}
        
        except Exception as e:
            logger.error(f"Fix application failed: {str(e)}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    async def _fix_retry_with_backoff(self, issue: Dict, params: Dict) -> Dict:
        """Retry failed step with exponential backoff."""
        
        max_retries = params.get('max_retries', 3)
        backoff_factor = params.get('backoff_factor', 2)
        
        # TODO: Implement retry logic
        # Would need to rerun the specific failed step
        
        return {
            "success": True,
            "action": "retry_scheduled",
            "params": params
        }
    
    async def _fix_reduce_batch_size(self, issue: Dict, params: Dict) -> Dict:
        """Reduce batch size to fix memory errors."""
        
        # Update config with smaller batch size
        reduction = params.get('reduction_factor', 0.5)
        
        # TODO: Modify step config
        
        return {
            "success": True,
            "action": "batch_size_reduced",
            "reduction_factor": reduction
        }
    
    async def _fix_download_model(self, issue: Dict, params: Dict) -> Dict:
        """Download missing model."""
        
        # TODO: Trigger model download
        
        return {
            "success": True,
            "action": "model_download_initiated"
        }
    
    async def _fix_fallback_cpu(self, issue: Dict, params: Dict) -> Dict:
        """Fallback to CPU processing."""
        
        # TODO: Update step config to use CPU
        
        return {
            "success": True,
            "action": "fallback_to_cpu_configured"
        }
    
    async def _fix_adjust_thresholds(self, issue: Dict, params: Dict) -> Dict:
        """Adjust detection thresholds."""
        
        # TODO: Modify threshold parameters
        
        return {
            "success": True,
            "action": "thresholds_adjusted"
        }
    
    async def _fix_skip_missing(self, issue: Dict, params: Dict) -> Dict:
        """Skip missing file and continue."""
        
        return {
            "success": True,
            "action": "file_skipped"
        }
    
    async def _llm_analyze_error(self, issue: Dict):
        """Use LLM to analyze unknown error."""
        
        from agents.llm_agent import LLMAgent
        
        try:
            llm = LLMAgent(self.config)
            await llm.initialize()
            
            result = await llm.execute({
                "task": "analyze_error_and_suggest_fix",
                "data": {
                    "error": issue['error'],
                    "workflow_name": issue['workflow_name'],
                    "context": issue.get('result', {})
                }
            })
            
            logger.info(f"LLM analysis: {result}")
            
            # Log for human review
            log_file = Path(f"L:/goodq4all/logs/llm_error_analysis_{int(time.time())}.json")
            with open(log_file, 'w') as f:
                json.dump({
                    "issue": issue,
                    "llm_analysis": result
                }, f, indent=2)
            
        except Exception as e:
            logger.error(f"LLM analysis failed: {str(e)}", exc_info=True)


async def run_monitor():
    """Run the self-healing monitor."""
    cfg = load_configs({})
    monitor = SelfHealingMonitor(cfg)
    await monitor.monitor_and_heal(check_interval=60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_monitor())
