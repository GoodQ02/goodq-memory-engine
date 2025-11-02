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
   Edit .env.agents and add your Azure OpenAI credentials

2. **Install DevUI (optional):**
   ```powershell
   conda activate goodq_agents
   pip install agent-framework-devui --pre
   ```

3. **Test Sample Agent:**
   ```powershell
   conda activate goodq_agents
   cd L:\goodq4all
   python agents/ingestion/scene_detector.py
   ```

4. **Read Full Guide:**
   See SPEC_TO_AGENTS_INTEGRATION_GUIDE.md for complete documentation

## Quick Start

```python
from agents.ingestion.scene_detector import SceneDetectorAgent

agent = SceneDetectorAgent()
result = await agent.execute({
    "video_path": "L:/_DATA/video.mp4"
})
```

## Resources

- Integration Guide: SPEC_TO_AGENTS_INTEGRATION_GUIDE.md
- Agent Framework Docs: https://learn.microsoft.com/agent-framework/
- Spec-to-Agents: https://github.com/microsoft/spec-to-agents
- Discord: https://discord.gg/b5zjErwbQM
