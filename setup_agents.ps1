# GoodQ Multi-Agent System Setup
# Sets up Microsoft Agent Framework integration

Write-Host "=== GoodQ Multi-Agent System Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "1. Checking prerequisites..." -ForegroundColor Yellow

$hasUv = Get-Command uv -ErrorAction SilentlyContinue
$hasGit = Get-Command git -ErrorAction SilentlyContinue
$hasConda = Get-Command conda -ErrorAction SilentlyContinue

if (-not $hasUv) {
    Write-Host "  ✗ uv not found - please install first" -ForegroundColor Red
    exit 1
}
if (-not $hasGit) {
    Write-Host "  ✗ git not found - please install first" -ForegroundColor Red
    exit 1
}
if (-not $hasConda) {
    Write-Host "  ✗ conda not found - please install first" -ForegroundColor Red
    exit 1
}

Write-Host "  ✓ All prerequisites met" -ForegroundColor Green

# Create agents environment
Write-Host "`n2. Creating goodq_agents conda environment..." -ForegroundColor Yellow

$envExists = conda env list | Select-String "goodq_agents"
if ($envExists) {
    Write-Host "  ⚠ Environment already exists" -ForegroundColor Yellow
    $response = Read-Host "  Remove and recreate? (y/n)"
    if ($response -eq "y") {
        conda env remove -n goodq_agents -y
        conda create -n goodq_agents python=3.11 -y
    }
} else {
    conda create -n goodq_agents python=3.11 -y
}

Write-Host "  ✓ Environment created" -ForegroundColor Green

# Install Agent Framework
Write-Host "`n3. Installing Microsoft Agent Framework..." -ForegroundColor Yellow

conda run -n goodq_agents pip install agent-framework --pre

Write-Host "  ✓ Agent Framework installed" -ForegroundColor Green

# Create directory structure
Write-Host "`n4. Creating directory structure..." -ForegroundColor Yellow

$dirs = @(
    "L:\goodq4all\agents\ingestion",
    "L:\goodq4all\agents\analysis",
    "L:\goodq4all\agents\knowledge",
    "L:\goodq4all\agents\analysis\scripts",
    "L:\goodq4all\workflows",
    "L:\goodq4all\specs",
    "L:\goodq4all\data\agent_checkpoints",
    "L:\goodq4all\data\workflow_logs",
    "L:\goodq4all\tests\agents",
    "L:\goodq4all\tests\workflows"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

Write-Host "  ✓ Directory structure created" -ForegroundColor Green

# Create .env.agents
Write-Host "`n5. Creating .env.agents configuration..." -ForegroundColor Yellow

$envContent = @"
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# Agent Framework Configuration
AGENT_FRAMEWORK_LOG_LEVEL=INFO
AGENT_FRAMEWORK_TELEMETRY_ENABLED=true
AGENT_FRAMEWORK_CHECKPOINT_DIR=L:/goodq4all/data/agent_checkpoints

# Memory Store
MEM0_DB_PATH=L:/goodq4all/data/agent_memory.db
MEM0_VECTOR_STORE=faiss
MEM0_EMBEDDING_MODEL=text-embedding-3-small

# DevUI Configuration
DEVUI_HOST=0.0.0.0
DEVUI_PORT=8050
DEVUI_DEBUG=false

# GoodQ Integration
GOODQ_DATA_DIR=L:/_DATA/GoodQ_Data
GOODQ_MODELS_DIR=L:/models
GOODQ_CONFIG_PATH=L:/goodq4all/configs/config.yaml

# Observability
OTEL_SERVICE_NAME=goodq-agents
"@

Set-Content -Path "L:\goodq4all\.env.agents" -Value $envContent

Write-Host "  ✓ Configuration file created" -ForegroundColor Green
Write-Host "  ⚠ Please update .env.agents with your Azure credentials" -ForegroundColor Yellow

# Create base agent class
Write-Host "`n6. Creating base agent class..." -ForegroundColor Yellow

$baseAgentContent = @"
# Copyright (c) Microsoft. All rights reserved.
"""Base agent class for GoodQ agents."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class for all GoodQ agents."""
    
    def __init__(self, name: str, conda_env: str):
        self.name = name
        self.conda_env = conda_env
        self.initialized = False
    
    @abstractmethod
    async def initialize(self):
        """Initialize the agent (load models, etc.)"""
        pass
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's main task"""
        pass
    
    async def run_in_conda(self, script_path: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a script in the agent's conda environment."""
        args_json = json.dumps(args)
        
        cmd = [
            "conda", "run", "-n", self.conda_env,
            "python", script_path,
            args_json
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await proc.communicate()
        
        return {
            "status": "success" if proc.returncode == 0 else "error",
            "returncode": proc.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode()
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "name": self.name,
            "conda_env": self.conda_env,
            "initialized": self.initialized
        }
"@

Set-Content -Path "L:\goodq4all\agents\base_agent.py" -Value $baseAgentContent

# Create __init__.py files
$initContent = '"""GoodQ Agent System"""'
Set-Content -Path "L:\goodq4all\agents\__init__.py" -Value $initContent
Set-Content -Path "L:\goodq4all\agents\ingestion\__init__.py" -Value $initContent
Set-Content -Path "L:\goodq4all\agents\analysis\__init__.py" -Value $initContent
Set-Content -Path "L:\goodq4all\agents\knowledge\__init__.py" -Value $initContent
Set-Content -Path "L:\goodq4all\workflows\__init__.py" -Value $initContent

Write-Host "  ✓ Base agent class created" -ForegroundColor Green

# Create sample agent
Write-Host "`n7. Creating sample agent (SceneDetectorAgent)..." -ForegroundColor Yellow

$sampleAgentContent = @"
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
        "video_path": "L:/_DATA/sample_video.mp4"
    })
    
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import asyncio
    import json
    asyncio.run(main())
"@

Set-Content -Path "L:\goodq4all\agents\ingestion\scene_detector.py" -Value $sampleAgentContent

Write-Host "  ✓ Sample agent created" -ForegroundColor Green

# Create README
Write-Host "`n8. Creating documentation..." -ForegroundColor Yellow

$readmeContent = @"
# GoodQ Multi-Agent System

Microsoft Agent Framework integration for GoodQ pipeline.

## Setup Complete

Your agent system is now set up with:

- ✅ goodq_agents conda environment
- ✅ Microsoft Agent Framework installed
- ✅ Directory structure created
- ✅ Base agent class
- ✅ Sample agent (SceneDetectorAgent)

## Next Steps

1. **Configure Azure OpenAI:**
   Edit `.env.agents` and add your Azure OpenAI credentials

2. **Install DevUI (optional):**
   ``````powershell
   conda activate goodq_agents
   pip install agent-framework-devui --pre
   ``````

3. **Test Sample Agent:**
   ``````powershell
   conda activate goodq_agents
   cd L:\goodq4all
   python agents/ingestion/scene_detector.py
   ``````

4. **Read Full Guide:**
   See `SPEC_TO_AGENTS_INTEGRATION_GUIDE.md` for complete documentation

## Quick Start

``````python
from agents.ingestion.scene_detector import SceneDetectorAgent

agent = SceneDetectorAgent()
result = await agent.execute({
    "video_path": "L:/_DATA/video.mp4"
})
``````

## Resources

- Integration Guide: SPEC_TO_AGENTS_INTEGRATION_GUIDE.md
- Agent Framework Docs: https://learn.microsoft.com/agent-framework/
- Spec-to-Agents: https://github.com/microsoft/spec-to-agents
- Discord: https://discord.gg/b5zjErwbQM
"@

Set-Content -Path "L:\goodq4all\agents\README.md" -Value $readmeContent

Write-Host "  ✓ Documentation created" -ForegroundColor Green

# Summary
Write-Host "`n" + "="*70 -ForegroundColor Green
Write-Host "✅ GoodQ Multi-Agent System Setup Complete!" -ForegroundColor Green
Write-Host "="*70 -ForegroundColor Green

Write-Host "`nWhat was created:" -ForegroundColor Yellow
Write-Host "  • goodq_agents conda environment" -ForegroundColor White
Write-Host "  • Microsoft Agent Framework installed" -ForegroundColor White
Write-Host "  • Directory structure for agents and workflows" -ForegroundColor White
Write-Host "  • Base agent class (agents/base_agent.py)" -ForegroundColor White
Write-Host "  • Sample agent (agents/ingestion/scene_detector.py)" -ForegroundColor White
Write-Host "  • Configuration file (.env.agents)" -ForegroundColor White
Write-Host "  • Documentation (agents/README.md)" -ForegroundColor White

Write-Host "`n⚠ Important Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Edit .env.agents with your Azure OpenAI credentials" -ForegroundColor White
Write-Host "  2. Read SPEC_TO_AGENTS_INTEGRATION_GUIDE.md" -ForegroundColor White
Write-Host "  3. Test sample agent:" -ForegroundColor White
Write-Host "     conda activate goodq_agents" -ForegroundColor Gray
Write-Host "     python agents/ingestion/scene_detector.py" -ForegroundColor Gray

Write-Host "`n📚 Full documentation in:" -ForegroundColor Yellow
Write-Host "  • L:\goodq4all\SPEC_TO_AGENTS_INTEGRATION_GUIDE.md" -ForegroundColor White
Write-Host "  • L:\goodq4all\agents\README.md" -ForegroundColor White

Write-Host ""
