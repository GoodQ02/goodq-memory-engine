"""
LLM Integration Module for GoodQ
Connects to multiple LLM endpoints with intelligent fallback
"""
import requests
from typing import Dict, Any, Optional, List

class LLMClient:
    def __init__(self, endpoints: List[Dict[str, str]] = None):
        """
        Initialize with multiple endpoints in priority order
        endpoints = [{"url": "http://localhost:8005/v1", "name": "vLLM"}, {"url": "http://localhost:11434/v1", "name": "Ollama"}]
        """
        if endpoints is None:
            # Default endpoints in priority order: vLLM (fast) -> Ollama -> LM Studio
            endpoints = [
                {"url": "http://localhost:8005/v1", "name": "vLLM-Llama-1B"},
                {"url": "http://localhost:11434/v1", "name": "Ollama-Phi4"},
                {"url": "http://localhost:1234/v1", "name": "LM-Studio"}
            ]
        
        self.endpoints = endpoints
        self.model = None
        self.active_endpoint = None
        self.available = self._find_healthy_endpoint()
        
    def _find_healthy_endpoint(self) -> bool:
        """Find first healthy endpoint with available models"""
        for endpoint in self.endpoints:
            try:
                response = requests.get(f"{endpoint['url']}/models", timeout=2)
                if response.ok:
                    data = response.json()
                    models = data.get('data', [])
                    if models:
                        # Found a healthy endpoint!
                        self.active_endpoint = endpoint
                        self.model = models[0]['id']
                        print(f"✓ {endpoint['name']} connected! Using model: {self.model}")
                        return True
            except Exception as e:
                # Silently try next endpoint
                pass
        
        print(f"⚠ No healthy LLM endpoints available")
        return False
    
    def chat(self, message: str, context: Dict[str, Any] = None) -> str:
        """Send a chat message to active LLM endpoint"""
        if not self.available or not self.active_endpoint:
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
            
            # Call active endpoint
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
                f"{self.active_endpoint['url']}/chat/completions",
                json=payload,
                timeout=30
            )
            
            if response.ok:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                print(f"{self.active_endpoint['name']} error: {response.status_code}")
                # Try to reconnect to a different endpoint
                self.available = self._find_healthy_endpoint()
                return None
                
        except Exception as e:
            print(f"Error calling {self.active_endpoint['name']}: {e}")
            # Try to reconnect to a different endpoint
            self.available = self._find_healthy_endpoint()
            return None
