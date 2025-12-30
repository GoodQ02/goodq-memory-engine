"""
GoodQ4All Production LLM Client
================================
Unified interface for vLLM (primary) and Ollama (fallback) with automatic failover,
health monitoring, and intelligent model selection.

Architecture:
- Primary: vLLM servers (WSL)
- Fallback: Ollama (WSL/Windows)
- Auto-recovery with exponential backoff
- Connection pooling and caching
- Comprehensive error handling and logging

Version: 1.0.0
"""

import os
import sys
import time
import logging
import requests
from typing import Optional, Dict, List, Any, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for an LLM model endpoint"""
    name: str
    base_url: str
    port: int
    model_id: str
    backend: Literal["vllm", "ollama"]
    vram_gb: float
    tokens_per_sec: int
    context_length: int
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0  # Higher = preferred
    
    @property
    def endpoint(self) -> str:
        """Full API endpoint URL"""
        return f"{self.base_url}:{self.port}/v1"
    
    def __repr__(self):
        return f"<ModelConfig {self.name} @ {self.endpoint}>"


@dataclass
class HealthStatus:
    """Health status for a model endpoint"""
    is_healthy: bool
    last_check: datetime
    response_time_ms: float
    consecutive_failures: int = 0
    last_error: Optional[str] = None


class LLMClient:
    """
    Production-grade LLM client with intelligent routing and failover
    
    Features:
    - Automatic health checks and failover
    - Model selection by capability/performance
    - Connection pooling and retry logic
    - Comprehensive logging and metrics
    - OpenAI-compatible API
    
    Example:
        client = LLMClient(
            models=[...],
            health_check_interval=60,
            max_retries=3,
            timeout=30,
            cache_ttl=300,
            enable_health_checks=False
        )
        response = client.chat(
            messages=[{"role": "user", "content": "Hello!"}],
            prefer_speed=True
        )
    """
    
    MODELS: List[ModelConfig] = []
    
    def __init__(
        self,
        *,
        models: List[ModelConfig],
        health_check_interval: int,
        max_retries: int,
        timeout: int,
        cache_ttl: int,
        enable_health_checks: bool
    ):
        """
        Initialize LLM client
        
        Args:
            health_check_interval: Seconds between health checks
            max_retries: Maximum retry attempts per request
            timeout: Request timeout in seconds
            cache_ttl: Health cache time-to-live in seconds
            enable_health_checks: Enable health monitoring (default: load from config)
        """
        if not models:
            raise ValueError("LLMClient requires a non-empty models list")
        if enable_health_checks is None:
            raise ValueError("LLMClient requires explicit enable_health_checks")

        self.MODELS = models
        self.health_check_interval = health_check_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.cache_ttl = cache_ttl

        self.health_checks_enabled = enable_health_checks
        
        # Health tracking
        self.health_status: Dict[str, HealthStatus] = {}
        self.last_health_check: Optional[datetime] = None
        
        # Track last used model
        self.last_model_used: Optional[ModelConfig] = None
        self.last_provider_used: Optional[str] = None
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "GoodQ4All-LLM-Client/1.0"
        })
        
        logger.info(f"LLMClient initialized with {len(self.MODELS)} models (health checks: {self.health_checks_enabled})")
        
        # Initial health check (only if enabled)
        if self.health_checks_enabled:
            self.check_all_health()

    @property
    def models(self) -> List[ModelConfig]:
        """Get list of all configured models"""
        return self.MODELS
    
    @property
    def available(self) -> bool:
        """Check if any models are available (healthy)"""
        if not self.health_status:
            self.check_all_health()
        return any(status.is_healthy for status in self.health_status.values())
    
    @property
    def model(self) -> Optional[str]:
        """Get the current/last active model name (alias for get_active_model)"""
        # If we've used a model, return it
        if self.last_model_used:
            return self.last_model_used.name
        
        # Otherwise, return the best available healthy model
        healthy = self.get_healthy_models()
        if healthy:
            return healthy[0].name
        
        return None
    
    def check_all_health(self, force: bool = False) -> Dict[str, HealthStatus]:
        """
        Check health of all model endpoints
        
        Args:
            force: Force check even if cache is valid
            
        Returns:
            Dictionary of model name -> health status
        """
        now = datetime.now()
        
        # Use cache if valid
        if not force and self.last_health_check:
            elapsed = (now - self.last_health_check).total_seconds()
            if elapsed < self.cache_ttl:
                logger.debug(f"Using cached health status ({elapsed:.1f}s old)")
                return self.health_status
        
        logger.debug("Performing health checks on all models...")
        
        for model in self.MODELS:
            start = time.time()
            try:
                # Check /v1/models endpoint
                response = self.session.get(
                    f"{model.endpoint}/models",
                    timeout=10  # Increased for WSL connectivity (can be slower)
                )
                response_time = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    self.health_status[model.name] = HealthStatus(
                        is_healthy=True,
                        last_check=now,
                        response_time_ms=response_time,
                        consecutive_failures=0
                    )
                    logger.debug(f"[OK] {model.name} healthy ({response_time:.0f}ms)")
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                # Update failure count
                prev_status = self.health_status.get(model.name)
                failures = prev_status.consecutive_failures + 1 if prev_status else 1
                
                self.health_status[model.name] = HealthStatus(
                    is_healthy=False,
                    last_check=now,
                    response_time_ms=0,
                    consecutive_failures=failures,
                    last_error=str(e)
                )
                # Silent health checks - only log once at startup
                if self.health_checks_enabled and failures == 1:
                    logger.debug(f"[SKIP] {model.name} not available: {str(e)}")
        
        self.last_health_check = now
        return self.health_status
    
    def get_healthy_models(
        self,
        capabilities: Optional[List[str]] = None,
        prefer_speed: bool = False,
        prefer_quality: bool = False
    ) -> List[ModelConfig]:
        """
        Get list of healthy models matching criteria
        
        Args:
            capabilities: Required capabilities (e.g., ["chat", "vision"])
            prefer_speed: Prioritize fastest models
            prefer_quality: Prioritize highest quality models
            
        Returns:
            List of healthy models sorted by priority
        """
        # Ensure health is current
        self.check_all_health()
        
        # Filter healthy models
        healthy = [
            model for model in self.MODELS
            if self.health_status.get(model.name, HealthStatus(False, datetime.now(), 0)).is_healthy
        ]
        
        # Filter by capabilities
        if capabilities:
            healthy = [
                model for model in healthy
                if all(cap in model.capabilities for cap in capabilities)
            ]
        
        # Sort by criteria
        if prefer_speed:
            healthy.sort(key=lambda m: m.tokens_per_sec, reverse=True)
        elif prefer_quality:
            healthy.sort(key=lambda m: (m.vram_gb, m.priority), reverse=True)
        else:
            healthy.sort(key=lambda m: m.priority, reverse=True)
        
        return healthy
    
    def select_model(
        self,
        capabilities: Optional[List[str]] = None,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
        model_name: Optional[str] = None
    ) -> Optional[ModelConfig]:
        """
        Select best available model
        
        Args:
            capabilities: Required capabilities
            prefer_speed: Prefer fastest model
            prefer_quality: Prefer highest quality model
            model_name: Force specific model by name
            
        Returns:
            Selected model or None if no healthy models available
        """
        # Force specific model
        if model_name:
            model = next((m for m in self.MODELS if m.name == model_name), None)
            if model:
                status = self.health_status.get(model.name)
                if status and status.is_healthy:
                    return model
                logger.warning(f"Requested model {model_name} is not healthy")
                return None
            logger.error(f"Model {model_name} not found")
            return None
        
        # Get healthy models matching criteria
        candidates = self.get_healthy_models(capabilities, prefer_speed, prefer_quality)
        
        if not candidates:
            logger.error("No healthy models available!")
            return None
        
        selected = candidates[0]
        logger.info(f"Selected model: {selected.name} ({selected.backend})")
        return selected
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model_name: Optional[str] = None,
        prefer_speed: bool = False,
        prefer_quality: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request with automatic model selection and failover
        
        Args:
            messages: Chat messages in OpenAI format
            model_name: Force specific model
            prefer_speed: Prefer fastest available model
            prefer_quality: Prefer highest quality model
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Enable streaming responses
            **kwargs: Additional parameters passed to API
            
        Returns:
            OpenAI-compatible response dict
            
        Raises:
            Exception: If all models fail
        """
        # Select model
        model = self.select_model(
            capabilities=["chat"],
            prefer_speed=prefer_speed,
            prefer_quality=prefer_quality,
            model_name=model_name
        )
        
        if not model:
            raise Exception("No healthy chat models available")
        
        # Build request
        payload = {
            "model": model.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            **kwargs
        }
        
        # Attempt request with retries
        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Chat request to {model.name} (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.session.post(
                    f"{model.endpoint}/chat/completions",
                    json=payload,
                    timeout=self.timeout,
                    stream=stream
                )
                
                if response.status_code == 200:
                    if stream:
                        return response  # Return response object for streaming
                    result = response.json()
                    
                    # Track successful model usage
                    self.last_model_used = model
                    self.last_provider_used = f"{model.backend}:{model.name}"
                    
                    logger.info(f"[OK] Chat response from {model.name}")
                    return result
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
                # Mark model as unhealthy
                if model.name in self.health_status:
                    self.health_status[model.name].is_healthy = False
                    self.health_status[model.name].consecutive_failures += 1
                
                # Try next model on subsequent attempts
                if attempt < self.max_retries - 1:
                    # Get next best model
                    candidates = self.get_healthy_models(
                        capabilities=["chat"],
                        prefer_speed=prefer_speed,
                        prefer_quality=prefer_quality
                    )
                    if candidates:
                        model = candidates[0]
                        logger.info(f"Failing over to {model.name}")
                    else:
                        break  # No more healthy models
                
                time.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception(f"All chat attempts failed. Last error: {last_error}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive client status
        
        Returns:
            Status dictionary with health info and metrics
        """
        self.check_all_health()
        
        healthy_count = sum(1 for s in self.health_status.values() if s.is_healthy)
        total_count = len(self.MODELS)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "models_total": total_count,
            "models_healthy": healthy_count,
            "models_unhealthy": total_count - healthy_count,
            "health_status": {
                name: {
                    "healthy": status.is_healthy,
                    "response_time_ms": status.response_time_ms,
                    "consecutive_failures": status.consecutive_failures,
                    "last_check": status.last_check.isoformat(),
                    "last_error": status.last_error
                }
                for name, status in self.health_status.items()
            },
            "models": [
                {
                    "name": m.name,
                    "backend": m.backend,
                    "endpoint": m.endpoint,
                    "model_id": m.model_id,
                    "vram_gb": m.vram_gb,
                    "tokens_per_sec": m.tokens_per_sec,
                    "capabilities": m.capabilities,
                    "priority": m.priority
                }
                for m in self.MODELS
            ]
        }
    
    def get_active_model(self) -> Optional[str]:
        """
        Get the name of the last successfully used model
        
        Returns:
            Model name or None if no model has been used yet
        """
        if self.last_model_used:
            return self.last_model_used.name
        return None
    
    def close(self):
        """Close client and cleanup resources"""
        self.session.close()
        logger.info("LLMClient closed")


# Singleton instance for easy import
_client_instance: Optional[LLMClient] = None


def get_client(
    *,
    models: List[ModelConfig],
    health_check_interval: int,
    max_retries: int,
    timeout: int,
    cache_ttl: int,
    enable_health_checks: bool,
) -> LLMClient:
    """Get or create singleton LLM client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient(
            models=models,
            health_check_interval=health_check_interval,
            max_retries=max_retries,
            timeout=timeout,
            cache_ttl=cache_ttl,
            enable_health_checks=enable_health_checks,
        )
    return _client_instance


# Convenience functions
def chat(messages: List[Dict[str, str]], *, client: LLMClient, **kwargs) -> Dict[str, Any]:
    """Convenience function for chat completion"""
    return client.chat(messages, **kwargs)


def get_status(*, client: LLMClient) -> Dict[str, Any]:
    """Convenience function for status check"""
    return client.get_status()


if __name__ == "__main__":
    # Test harness requires explicit injection
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    print("\n" + "="*70)
    print("GoodQ4All LLM Client Test")
    print("="*70 + "\n")
    print("[SKIP] This test requires an injected LLMClient configuration.")
    sys.exit(0)
    
    # Show status
    status = client.get_status()
    print(f"[OK] Models: {status['models_healthy']}/{status['models_total']} healthy\n")
    
    # Test chat
    print("Testing chat with speed preference...")
    try:
        response = client.chat(
            messages=[{"role": "user", "content": "Say 'Hello from GoodQ4All!' in one sentence."}],
            prefer_speed=True,
            max_tokens=50
        )
        content = response['choices'][0]['message']['content']
        print(f"\n[OK] Response: {content}\n")
    except Exception as e:
        print(f"\n[FAIL] Error: {e}\n")
    
    print("="*70)
