"""
LLM Agent - Provides LLM capabilities for analysis, summarization, and self-healing
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
import sys
import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class LLMAgent(BaseAgent):
    """Agent that provides LLM capabilities via LM Studio."""
    
    def __init__(self, cfg: Dict[str, Any]):
        super().__init__(
            name="LLMAgent",
            conda_env="base"  # LLM calls don't need special env
        )
        self.config = cfg
        self.llm_config = self.config.get('llm', {})
        self.api_url = self.llm_config.get('api_url', 'http://localhost:1234/v1/chat/completions')
        self.model_id = self.llm_config.get('model_id', 'LM_STUDIO_GOODQ')
        self.timeout = self.llm_config.get('timeout', 30)
        self.temperature = self.llm_config.get('temperature', 0.3)
        self.max_tokens = self.llm_config.get('max_tokens', 500)
    
    async def initialize(self):
        """Initialize LLM agent - check if LM Studio is available."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://localhost:1234/v1/models",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        logger.info("LM Studio is available")
                        self.initialized = True
                    else:
                        logger.warning(f"LM Studio returned status {response.status}")
                        self.initialized = False
        except Exception as e:
            logger.error(f"Failed to connect to LM Studio: {str(e)}")
            self.initialized = False
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute LLM task.
        
        Args:
            input_data: {
                "task": str,  # Task type
                "data": Dict,  # Task-specific data
                "system_prompt": str (optional),
                "temperature": float (optional),
                "max_tokens": int (optional)
            }
        
        Returns:
            Task-specific results
        """
        if not self.initialized:
            await self.initialize()
        
        if not self.initialized:
            return {
                "status": "error",
                "error": "LLM not available - LM Studio not running"
            }
        
        task = input_data.get('task')
        data = input_data.get('data', {})
        
        # Route to appropriate task handler
        task_handlers = {
            "summarize_scene": self._summarize_scene,
            "summarize_video": self._summarize_video,
            "extract_relationships": self._extract_relationships,
            "analyze_emotion_arc": self._analyze_emotion_arc,
            "analyze_error_and_suggest_fix": self._analyze_error,
            "extract_entities": self._extract_entities,
            "generate_description": self._generate_description
        }
        
        handler = task_handlers.get(task)
        if not handler:
            return {
                "status": "error",
                "error": f"Unknown task: {task}"
            }
        
        try:
            result = await handler(data, input_data)
            return {
                "status": "success",
                "task": task,
                "result": result
            }
        except Exception as e:
            logger.error(f"LLM task {task} failed: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "task": task,
                "error": str(e)
            }
    
    async def _call_llm(self, messages: List[Dict], temperature: float = None, max_tokens: int = None) -> str:
        """Make LLM API call."""
        
        temperature = temperature or self.temperature
        max_tokens = max_tokens or self.max_tokens
        
        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        error_text = await response.text()
                        raise Exception(f"LLM API error {response.status}: {error_text}")
        
        except asyncio.TimeoutError:
            raise Exception(f"LLM request timed out after {self.timeout}s")
        except Exception as e:
            raise Exception(f"LLM API call failed: {str(e)}")
    
    async def _summarize_scene(self, data: Dict, config: Dict) -> Dict:
        """Summarize a single scene."""
        
        scene_data = data.get('scene', {})
        objects = data.get('objects', [])
        faces = data.get('faces', [])
        transcription = data.get('transcription', '')
        
        prompt = f"""Summarize this video scene in 2-3 sentences:

Scene duration: {scene_data.get('duration', 0):.1f} seconds
Objects detected: {', '.join(objects[:10]) if objects else 'none'}
Faces detected: {len(faces)}
Dialogue: {transcription if transcription else 'no dialogue'}

Provide a concise, vivid description focusing on the main action or subject."""

        messages = [
            {"role": "system", "content": "You are a video analyst providing concise scene summaries."},
            {"role": "user", "content": prompt}
        ]
        
        summary = await self._call_llm(messages, max_tokens=150)
        
        return {
            "summary": summary.strip(),
            "scene_number": scene_data.get('scene_number'),
            "duration": scene_data.get('duration')
        }
    
    async def _summarize_video(self, data: Dict, config: Dict) -> Dict:
        """Summarize entire video."""
        
        scene_summaries = data.get('scene_summaries', [])
        full_transcription = data.get('transcription', '')
        video_info = data.get('video_info', {})
        
        scenes_text = "\n".join([
            f"Scene {i+1}: {s.get('summary', '')}"
            for i, s in enumerate(scene_summaries)
        ])
        
        prompt = f"""Summarize this video in 3-4 sentences:

Video: {video_info.get('filename', 'Unknown')}
Duration: {video_info.get('duration', 0):.1f} seconds
Scenes: {len(scene_summaries)}

Scene summaries:
{scenes_text}

Provide an engaging overview that captures the essence and main themes."""

        messages = [
            {"role": "system", "content": "You are a video analyst providing engaging video summaries."},
            {"role": "user", "content": prompt}
        ]
        
        summary = await self._call_llm(messages, max_tokens=250)
        
        return {
            "summary": summary.strip(),
            "total_scenes": len(scene_summaries),
            "duration": video_info.get('duration')
        }
    
    async def _extract_relationships(self, data: Dict, config: Dict) -> Dict:
        """Extract relationships between entities."""
        
        entities = data.get('entities', [])
        context = data.get('context', '')
        
        if len(entities) < 2:
            return {"relationships": []}
        
        entities_text = ', '.join([f"{e.get('name')} ({e.get('type')})" for e in entities])
        
        prompt = f"""Identify relationships between these entities based on the context:

Entities: {entities_text}

Context: {context}

Format each relationship as: Entity1 | RELATIONSHIP_TYPE | Entity2
Examples:
- John | SPEAKS_WITH | Sarah
- Dog | BELONGS_TO | John
- Chicago | LOCATION_OF | Event

List only clear, observable relationships:"""

        messages = [
            {"role": "system", "content": "You are an analyst identifying entity relationships."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_llm(messages, max_tokens=300)
        
        # Parse relationships
        relationships = []
        for line in response.strip().split('\n'):
            line = line.strip('- ').strip()
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) == 3:
                    relationships.append({
                        "source": parts[0],
                        "relationship": parts[1],
                        "target": parts[2]
                    })
        
        return {"relationships": relationships}
    
    async def _analyze_emotion_arc(self, data: Dict, config: Dict) -> Dict:
        """Analyze emotional arc of video."""
        
        scenes = data.get('scenes', [])
        emotions_by_scene = data.get('emotions_by_scene', [])
        transcription = data.get('transcription', '')
        
        scenes_text = "\n".join([
            f"Scene {i+1}: {s.get('summary', '')} - Emotions: {e}"
            for i, (s, e) in enumerate(zip(scenes, emotions_by_scene))
        ])
        
        prompt = f"""Analyze the emotional arc of this video:

{scenes_text}

Describe:
1. Overall emotional tone
2. Key emotional shifts
3. Emotional climax or resolution
4. Viewer emotional journey

Keep response to 3-4 sentences:"""

        messages = [
            {"role": "system", "content": "You are an emotional intelligence analyst."},
            {"role": "user", "content": prompt}
        ]
        
        analysis = await self._call_llm(messages, max_tokens=200)
        
        return {
            "emotional_arc": analysis.strip(),
            "scenes_analyzed": len(scenes)
        }
    
    async def _analyze_error(self, data: Dict, config: Dict) -> Dict:
        """Analyze error and suggest fix."""
        
        step_name = data.get('step_name')
        error = data.get('error')
        context = data.get('context', {})
        
        prompt = f"""Analyze this pipeline error and suggest a fix:

Step: {step_name}
Error: {error}
Context: {json.dumps(context, indent=2)}

Provide:
1. Root cause analysis
2. Suggested fix type: 'retry_with_params', 'skip', or 'manual_intervention'
3. If retry_with_params: what parameters to modify
4. Brief reasoning

Format as JSON."""

        messages = [
            {"role": "system", "content": "You are a debugging assistant analyzing pipeline errors."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_llm(messages, max_tokens=400, temperature=0.1)
        
        # Try to parse JSON response
        try:
            analysis = json.loads(response)
        except:
            # If not valid JSON, return structured error
            analysis = {
                "root_cause": response,
                "suggested_fix": {
                    "type": "manual_intervention",
                    "reason": "Could not parse automated fix suggestion"
                }
            }
        
        return analysis
    
    async def _extract_entities(self, data: Dict, config: Dict) -> Dict:
        """Extract named entities from text."""
        
        text = data.get('text', '')
        context = data.get('context', '')
        
        prompt = f"""Extract named entities from this text:

Text: {text}

Context: {context}

Identify:
- PERSON: People's names
- LOCATION: Places, cities, countries
- ORGANIZATION: Companies, institutions
- DATE: Specific dates or time periods
- EVENT: Named events
- OBJECT: Significant objects

Format as JSON list: [{"name": "...", "type": "...", "context": "..."}]"""

        messages = [
            {"role": "system", "content": "You are a named entity recognition system."},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._call_llm(messages, max_tokens=400)
        
        try:
            entities = json.loads(response)
        except:
            # Parse from text format
            entities = []
            for line in response.split('\n'):
                if ':' in line:
                    parts = line.strip('- ').split(':')
                    if len(parts) >= 2:
                        entities.append({
                            "name": parts[1].strip(),
                            "type": parts[0].strip()
                        })
        
        return {"entities": entities}
    
    async def _generate_description(self, data: Dict, config: Dict) -> Dict:
        """Generate natural language description."""
        
        data_points = data.get('data_points', {})
        context = data.get('context', '')
        style = data.get('style', 'concise')
        
        prompt = f"""Generate a {style} description based on this data:

{json.dumps(data_points, indent=2)}

Context: {context}

Provide a natural, engaging description:"""

        messages = [
            {"role": "system", "content": f"You are a {style} content writer."},
            {"role": "user", "content": prompt}
        ]
        
        description = await self._call_llm(messages)
        
        return {"description": description.strip()}
