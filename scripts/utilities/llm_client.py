"""
LLM Integration Module for GoodQ
Connects to LM Studio for intelligent responses
"""
import requests
from typing import Dict, Any, Optional

class LLMClient:
    def __init__(self, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url
        self.model = None
        self.available = self._check_availability()
        
    def _check_availability(self) -> bool:
        """Check if LM Studio is running and has models loaded"""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=2)
            if response.ok:
                data = response.json()
                models = data.get('data', [])
                if models:
                    # Use first available model
                    self.model = models[0]['id']
                    print(f"✓ LM Studio connected! Using model: {self.model}")
                    return True
            return False
        except Exception as e:
            print(f"⚠ LM Studio not available: {e}")
            return False
    
    def chat(self, message: str, context: Dict[str, Any] = None) -> str:
        """Send a chat message to LM Studio"""
        if not self.available:
            return None
            
        try:
            # Build system prompt with context
            system_prompt = """You are GoodQ, an intelligent personal memory assistant. 
You help users explore and understand their video memories, knowledge graph, and personal data.

IMPORTANT: When the user asks for specific data (names, entities, scenes, etc.), tell them you'll query the database.
DO NOT make up fake names or data. Instead, acknowledge what data is available and suggest what can be queried.

Available data in context:
- Scenes count
- Embeddings count  
- Entities count
- Relationships count
- Processing status

Be conversational, helpful, and HONEST. When discussing memories or data:
- Reference actual numbers from context when available
- Be empathetic about emotional content (this is family home movies!)
- Suggest what CAN be queried from the database
- NEVER invent fake entity names
- Keep responses concise but informative
"""
            
            # Add context if available
            if context:
                context_str = "\n\nCurrent Context:\n"
                for key, value in context.items():
                    if isinstance(value, dict):
                        context_str += f"- {key}:\n"
                        for k, v in value.items():
                            context_str += f"  - {k}: {v}\n"
                    else:
                        context_str += f"- {key}: {value}\n"
                system_prompt += context_str
            
            # Call LM Studio
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                "temperature": 0.7,
                "max_tokens": 500,
                "stream": False
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=30
            )
            
            if response.ok:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                print(f"LM Studio error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error calling LM Studio: {e}")
            return None
