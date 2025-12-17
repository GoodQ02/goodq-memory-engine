"""
GoodQ Agent Orchestrator
Coordinates multi-agent workflows with self-healing and LLM integration
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import sqlite3
import logging

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates multi-agent workflows with self-healing capabilities."""
    
    def __init__(self, cfg: Dict[str, Any]):
        self.config = cfg
        paths = (self.config.get("paths") or {}) if isinstance(self.config, dict) else {}
        self.db_path = Path(paths.get("db_path") or "L:/_DATA/GoodQ_Data/memory.db")
        self.log_dir = Path(paths.get("log_dir") or "L:/goodq4all/logs")
        self.agents = {}
        self.workflow_history = []
        
    async def register_agent(self, agent_name: str, agent_instance):
        """Register an agent with the orchestrator."""
        logger.info(f"Registering agent: {agent_name}")
        self.agents[agent_name] = agent_instance
        await agent_instance.initialize()
    
    async def execute_workflow(self, workflow_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow across multiple agents.
        
        Args:
            workflow_name: Name of workflow (e.g., "video_ingestion")
            input_data: Initial workflow data
            
        Returns:
            Workflow results with all agent outputs
        """
        start_time = time.time()
        workflow_id = f"{workflow_name}_{int(start_time)}"
        
        logger.info(f"Starting workflow: {workflow_id}")
        
        workflow_result = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "start_time": datetime.now().isoformat(),
            "status": "running",
            "steps": [],
            "errors": []
        }
        
        try:
            # Load workflow definition
            workflow_def = await self._load_workflow_definition(workflow_name)
            
            # Execute each step
            context = input_data.copy()
            for step in workflow_def['steps']:
                step_result = await self._execute_step(step, context, workflow_id)
                workflow_result['steps'].append(step_result)
                
                # Check for errors and attempt self-healing
                if step_result['status'] == 'error':
                    logger.warning(f"Step {step['name']} failed, attempting self-heal")
                    heal_result = await self._self_heal_step(step, context, step_result)
                    
                    if heal_result['status'] == 'success':
                        logger.info(f"Self-heal successful for {step['name']}")
                        step_result = heal_result
                        workflow_result['steps'][-1] = step_result
                    else:
                        logger.error(f"Self-heal failed for {step['name']}")
                        if step.get('required', True):
                            workflow_result['status'] = 'failed'
                            workflow_result['errors'].append({
                                "step": step['name'],
                                "error": step_result.get('error'),
                                "heal_attempted": True,
                                "heal_result": heal_result
                            })
                            break
                
                # Merge step output into context
                if 'output' in step_result:
                    context.update(step_result['output'])
            
            # Mark as complete if no failures
            if workflow_result['status'] != 'failed':
                workflow_result['status'] = 'complete'
            
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {str(e)}", exc_info=True)
            workflow_result['status'] = 'failed'
            workflow_result['errors'].append({
                "type": "workflow_error",
                "error": str(e)
            })
        
        finally:
            workflow_result['end_time'] = datetime.now().isoformat()
            workflow_result['duration_seconds'] = time.time() - start_time
            
            # Save workflow result
            await self._save_workflow_result(workflow_result)
            
        return workflow_result
    
    async def _execute_step(self, step: Dict, context: Dict, workflow_id: str) -> Dict[str, Any]:
        """Execute a single workflow step."""
        step_name = step['name']
        agent_name = step['agent']
        
        logger.info(f"Executing step: {step_name} with agent: {agent_name}")
        
        step_start = time.time()
        
        try:
            # Get agent
            if agent_name not in self.agents:
                raise ValueError(f"Agent {agent_name} not registered")
            
            agent = self.agents[agent_name]
            
            # Prepare input from context
            step_input = {}
            if 'inputs' in step:
                for key, value in step['inputs'].items():
                    # Support context variable substitution
                    if isinstance(value, str) and value.startswith('$'):
                        var_name = value[1:]
                        step_input[key] = context.get(var_name)
                    else:
                        step_input[key] = value
            else:
                step_input = context
            
            # Execute agent
            result = await agent.execute(step_input)
            
            return {
                "name": step_name,
                "agent": agent_name,
                "status": "success",
                "duration_seconds": time.time() - step_start,
                "output": result
            }
            
        except Exception as e:
            logger.error(f"Step {step_name} failed: {str(e)}", exc_info=True)
            return {
                "name": step_name,
                "agent": agent_name,
                "status": "error",
                "duration_seconds": time.time() - step_start,
                "error": str(e)
            }
    
    async def _self_heal_step(self, step: Dict, context: Dict, error_result: Dict) -> Dict[str, Any]:
        """Attempt to self-heal a failed step using LLM analysis."""
        
        if not self.config['llm'].get('enabled', False):
            logger.warning("LLM not enabled, cannot self-heal")
            return error_result
        
        # Use LLM to analyze error and suggest fix
        llm_agent = self.agents.get('llm_analyzer')
        if not llm_agent:
            logger.warning("LLM analyzer agent not available")
            return error_result
        
        try:
            analysis_input = {
                "step_name": step['name'],
                "agent_name": step['agent'],
                "error": error_result.get('error'),
                "context": context,
                "step_definition": step
            }
            
            analysis = await llm_agent.execute({
                "task": "analyze_error_and_suggest_fix",
                "data": analysis_input
            })
            
            # If LLM suggests a fix, attempt it
            if analysis.get('suggested_fix'):
                logger.info(f"Applying suggested fix: {analysis['suggested_fix']['description']}")
                
                # Apply fix based on suggestion
                fix_result = await self._apply_fix(step, context, analysis['suggested_fix'])
                return fix_result
            
        except Exception as e:
            logger.error(f"Self-heal analysis failed: {str(e)}", exc_info=True)
        
        return error_result
    
    async def _apply_fix(self, step: Dict, context: Dict, fix: Dict) -> Dict[str, Any]:
        """Apply a suggested fix to a failed step."""
        
        fix_type = fix.get('type')
        
        if fix_type == 'retry_with_params':
            # Retry with modified parameters
            modified_step = step.copy()
            modified_step['inputs'] = fix.get('modified_inputs', step.get('inputs', {}))
            return await self._execute_step(modified_step, context, "retry")
        
        elif fix_type == 'skip':
            # Skip this step and continue
            return {
                "name": step['name'],
                "status": "skipped",
                "reason": fix.get('reason')
            }
        
        else:
            logger.warning(f"Unknown fix type: {fix_type}")
            return {"status": "error", "error": "Unknown fix type"}
    
    async def _load_workflow_definition(self, workflow_name: str) -> Dict:
        """Load workflow definition from file."""
        workflow_path = Path(f"L:/goodq4all/workflows/{workflow_name}.yaml")
        
        if not workflow_path.exists():
            # Return default video ingestion workflow
            return self._get_default_video_workflow()
        
        import yaml
        with open(workflow_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _get_default_video_workflow(self) -> Dict:
        """Return default video ingestion workflow."""
        return {
            "name": "video_ingestion",
            "description": "Complete video ingestion and analysis pipeline",
            "steps": [
                {
                    "name": "scene_detection",
                    "agent": "scene_detector",
                    "inputs": {"video_path": "$video_path"},
                    "required": True
                },
                {
                    "name": "frame_extraction",
                    "agent": "frame_extractor",
                    "inputs": {
                        "video_path": "$video_path",
                        "scenes": "$scenes"
                    },
                    "required": True
                },
                {
                    "name": "object_detection",
                    "agent": "object_detector",
                    "inputs": {"frames": "$frames"},
                    "required": False
                },
                {
                    "name": "face_detection",
                    "agent": "face_detector",
                    "inputs": {"frames": "$frames"},
                    "required": False
                },
                {
                    "name": "audio_transcription",
                    "agent": "audio_transcriber",
                    "inputs": {"video_path": "$video_path"},
                    "required": True
                },
                {
                    "name": "emotion_analysis",
                    "agent": "emotion_analyzer",
                    "inputs": {
                        "video_path": "$video_path",
                        "transcription": "$transcription"
                    },
                    "required": False
                },
                {
                    "name": "llm_summarization",
                    "agent": "llm_summarizer",
                    "inputs": {
                        "scenes": "$scenes",
                        "objects": "$objects",
                        "faces": "$faces",
                        "transcription": "$transcription",
                        "emotions": "$emotions"
                    },
                    "required": True
                },
                {
                    "name": "knowledge_graph_update",
                    "agent": "kg_updater",
                    "inputs": {
                        "video_path": "$video_path",
                        "summary": "$summary",
                        "entities": "$entities",
                        "relationships": "$relationships"
                    },
                    "required": True
                }
            ]
        }
    
    async def _save_workflow_result(self, result: Dict):
        """Save workflow result to database and log file."""
        
        # Save to log file
        log_file = self.log_dir / f"workflow_{result['workflow_id']}.json"
        with open(log_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Create table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    workflow_id TEXT PRIMARY KEY,
                    workflow_name TEXT,
                    status TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds REAL,
                    steps_completed INTEGER,
                    errors_count INTEGER,
                    result_json TEXT
                )
            """)
            
            cursor.execute("""
                INSERT OR REPLACE INTO workflow_executions
                (workflow_id, workflow_name, status, start_time, end_time, 
                 duration_seconds, steps_completed, errors_count, result_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result['workflow_id'],
                result['workflow_name'],
                result['status'],
                result['start_time'],
                result['end_time'],
                result['duration_seconds'],
                len(result['steps']),
                len(result['errors']),
                json.dumps(result)
            ))
            
            conn.commit()
            
        finally:
            conn.close()
    
    async def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get status of a workflow execution."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT result_json FROM workflow_executions WHERE workflow_id = ?",
                (workflow_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return json.loads(row[0])
            return None
            
        finally:
            conn.close()
    
    async def get_agent_health(self) -> Dict[str, Any]:
        """Get health status of all registered agents."""
        health = {
            "timestamp": datetime.now().isoformat(),
            "agents": {}
        }
        
        for name, agent in self.agents.items():
            try:
                status = await agent.get_status()
                health['agents'][name] = {
                    "status": "healthy",
                    "initialized": status.get('initialized', False),
                    "details": status
                }
            except Exception as e:
                health['agents'][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return health
