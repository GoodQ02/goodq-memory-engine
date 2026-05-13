# Copyright (c) Microsoft. All rights reserved.
"""Scene Detector Agent - Detects scene boundaries in videos."""

from pathlib import Path
from typing import Dict, Any, List
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent


class SceneDetectorAgent(BaseAgent):
    """Detects scene boundaries in video files."""
    
    def __init__(self):
        super().__init__(
            name="SceneDetectorAgent",
            conda_env="goodq_video_scene_detect"
        )
    
    async def initialize(self):
        """Initialize scene detection agent."""
        # Verify conda environment has required packages
        result = await self.run_in_conda(
            str(Path(__file__).parent.parent / "check_scene_detect.py"),
            {}
        )
        
        if result["returncode"] == 0:
            self.initialized = True
        else:
            raise RuntimeError(f"Failed to initialize: {result['stderr']}")
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect scenes in video.
        
        Args:
            input_data: {
                "video_path": str,
                "threshold": float (optional),
                "min_scene_len": int (optional)
            }
        
        Returns:
            {
                "scenes": List[Dict],
                "total_scenes": int,
                "processing_time": float
            }
        """
        if not self.initialized:
            await self.initialize()
        
        video_path = input_data["video_path"]
        threshold = input_data.get("threshold", 27.0)
        min_scene_len = input_data.get("min_scene_len", 15)
        
        # Run scene detection in conda environment
        script_path = Path(__file__).parent / "scripts" / "detect_scenes.py"
        
        result = await self.run_in_conda(
            str(script_path),
            {
                "video_path": video_path,
                "threshold": threshold,
                "min_scene_len": min_scene_len
            }
        )
        
        if result["status"] == "success":
            return json.loads(result["stdout"])
        else:
            return {
                "status": "error",
                "error": result["stderr"]
            }


# Example usage
async def main():
    agent = SceneDetectorAgent()
    
    result = await agent.execute({
        "video_path": str(Path("GoodQ_Data") / "sample_video.mp4")
    })
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    import json
    asyncio.run(main())
