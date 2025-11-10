"""
Pipeline Agent Integration
Connects existing pipeline steps to the agent orchestrator
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.orchestrator import AgentOrchestrator
from agents.llm_agent import LLMAgent
from agents.base_agent import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineStepAgent(BaseAgent):
    """Generic agent wrapper for existing pipeline steps."""
    
    def __init__(self, step_name: str, conda_env: str, script_path: str):
        super().__init__(name=step_name, conda_env=conda_env)
        self.script_path = Path(script_path)
    
    async def initialize(self):
        """Verify script exists."""
        if not self.script_path.exists():
            raise FileNotFoundError(f"Script not found: {self.script_path}")
        self.initialized = True
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the pipeline step script."""
        if not self.initialized:
            await self.initialize()
        
        result = await self.run_in_conda(str(self.script_path), input_data)
        
        if result['status'] == 'success':
            # Parse output
            import json
            try:
                output = json.loads(result['stdout'])
                return output
            except:
                return {"raw_output": result['stdout']}
        else:
            raise Exception(result['stderr'])


async def setup_pipeline_agents() -> AgentOrchestrator:
    """Set up all pipeline agents."""
    
    orchestrator = AgentOrchestrator()
    
    # Register LLM agent
    llm_agent = LLMAgent()
    await orchestrator.register_agent('llm_analyzer', llm_agent)
    await orchestrator.register_agent('llm_summarizer', llm_agent)
    
    # Register scene detection agent
    scene_agent = PipelineStepAgent(
        step_name="scene_detector",
        conda_env="goodq_video_scene_detect",
        script_path="L:/goodq4all/steps/video_scene_detect/step.py"
    )
    await orchestrator.register_agent('scene_detector', scene_agent)
    
    # Register frame extraction agent (part of video ingest)
    frame_agent = PipelineStepAgent(
        step_name="frame_extractor",
        conda_env="goodq_video_scene_detect",
        script_path="L:/goodq4all/steps/video_ingest/step.py"
    )
    await orchestrator.register_agent('frame_extractor', frame_agent)
    
    # Register object detection agent
    object_agent = PipelineStepAgent(
        step_name="object_detector",
        conda_env="goodq_object_detect",
        script_path="L:/goodq4all/steps/object_detect/step.py"
    )
    await orchestrator.register_agent('object_detector', object_agent)
    
    # Register face detection agent
    face_agent = PipelineStepAgent(
        step_name="face_detector",
        conda_env="goodq_face_embed",
        script_path="L:/goodq4all/steps/face_embed/step.py"
    )
    await orchestrator.register_agent('face_detector', face_agent)
    
    # Register audio transcription agent
    transcribe_agent = PipelineStepAgent(
        step_name="audio_transcriber",
        conda_env="goodq_audio_transcribe",
        script_path="L:/goodq4all/steps/audio_transcribe/step.py"
    )
    await orchestrator.register_agent('audio_transcriber', transcribe_agent)
    
    # Register emotion analysis agent
    emotion_agent = PipelineStepAgent(
        step_name="emotion_analyzer",
        conda_env="goodq_emotion_classify",
        script_path="L:/goodq4all/steps/emotion_classify/step.py"
    )
    await orchestrator.register_agent('emotion_analyzer', emotion_agent)
    
    # Register knowledge graph agent
    kg_agent = PipelineStepAgent(
        step_name="kg_updater",
        conda_env="base",
        script_path="L:/goodq4all/steps/graph_builder/graph_builder.py"
    )
    await orchestrator.register_agent('kg_updater', kg_agent)
    
    logger.info("All pipeline agents registered")
    
    return orchestrator


async def process_video_with_agents(video_path: str) -> Dict[str, Any]:
    """
    Process a video through the agent orchestrator.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Complete processing results
    """
    orchestrator = await setup_pipeline_agents()
    
    # Execute workflow
    result = await orchestrator.execute_workflow(
        workflow_name="video_ingestion",
        input_data={"video_path": video_path}
    )
    
    return result


async def check_agent_health() -> Dict[str, Any]:
    """Check health of all agents."""
    orchestrator = await setup_pipeline_agents()
    return await orchestrator.get_agent_health()


async def main():
    """Test agent setup."""
    import json
    
    print("Setting up agents...")
    orchestrator = await setup_pipeline_agents()
    
    print("\nChecking agent health...")
    health = await orchestrator.get_agent_health()
    print(json.dumps(health, indent=2))
    
    print("\nTesting with sample video...")
    test_video = "L:/goodq4all/import_inbox/sample.mp4"
    
    if Path(test_video).exists():
        result = await process_video_with_agents(test_video)
        print(f"\nWorkflow {result['workflow_id']} completed with status: {result['status']}")
        print(f"Steps completed: {len(result['steps'])}")
        print(f"Errors: {len(result['errors'])}")
        
        # Save detailed result
        result_file = Path(f"L:/goodq4all/logs/agent_test_{result['workflow_id']}.json")
        with open(result_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nDetailed results saved to: {result_file}")
    else:
        print(f"Test video not found: {test_video}")


if __name__ == "__main__":
    asyncio.run(main())
