"""
GoodQ4All Model Health Status API
==================================
REST API endpoint for real-time LLM model health monitoring

Provides:
- Live health status for all vLLM and Ollama models
- Response time metrics
- Failure tracking
- JSON endpoint for dashboard integration

Usage:
    python api/health_status.py
    
    Then access: http://localhost:5050/api/health

Author: GoodQ4All Team
Date: 2025-11-18
"""

import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from llm_client import LLMClient
from flask import Flask, jsonify
from flask_cors import CORS
import logging
import threading
import time
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app,  # Enable CORS for dashboard access
     resources={r"/api/*": {"origins": "*"}},
     methods=["GET", "HEAD", "OPTIONS"])

# Cache for health status
_health_cache = {}
_cache_lock = threading.Lock()
_last_update = None
CACHE_TTL_SECONDS = 5  # Update every 5 seconds

# Initialize LLM client (singleton)
llm_client = None


def get_client():
    """Get or create LLM client instance"""
    global llm_client
    if llm_client is None:
        logger.info("Initializing LLM client...")
        llm_client = LLMClient()
        logger.info(f"LLM client initialized with {len(llm_client.MODELS)} models")
    return llm_client


def update_health_cache():
    """Background thread to update health cache"""
    global _health_cache, _last_update
    
    while True:
        try:
            client = get_client()
            
            # Force fresh health check
            health_status = client.check_all_health(force=True)
            
            # Build response
            models_data = []
            for model in client.MODELS:
                status = health_status.get(model.name)
                if status:
                    models_data.append({
                        'name': model.name,
                        'endpoint': model.endpoint,
                        'backend': model.backend,
                        'port': model.port,
                        'model_id': model.model_id,
                        'is_healthy': status.is_healthy,
                        'response_time_ms': round(status.response_time_ms, 1),
                        'consecutive_failures': status.consecutive_failures,
                        'last_error': status.last_error,
                        'last_check': status.last_check.isoformat(),
                        'capabilities': model.capabilities,
                        'vram_gb': model.vram_gb,
                        'tokens_per_sec': model.tokens_per_sec,
                        'context_length': model.context_length,
                        'priority': model.priority,
                    })
            
            # Calculate summary stats
            healthy_count = sum(1 for m in models_data if m['is_healthy'])
            vllm_count = sum(1 for m in models_data if m['backend'] == 'vllm')
            ollama_count = sum(1 for m in models_data if m['backend'] == 'ollama')
            vllm_healthy = sum(1 for m in models_data if m['backend'] == 'vllm' and m['is_healthy'])
            ollama_healthy = sum(1 for m in models_data if m['backend'] == 'ollama' and m['is_healthy'])
            
            response = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_models': len(models_data),
                'healthy_models': healthy_count,
                'unhealthy_models': len(models_data) - healthy_count,
                'vllm_total': vllm_count,
                'vllm_healthy': vllm_healthy,
                'ollama_total': ollama_count,
                'ollama_healthy': ollama_healthy,
                'models': models_data,
            }
            
            with _cache_lock:
                _health_cache = response
                _last_update = time.time()
                
            logger.info(f"Health cache updated: {healthy_count}/{len(models_data)} healthy")
        except Exception as e:
            logger.error(f"Error updating health cache: {e}")
        
        time.sleep(CACHE_TTL_SECONDS)


# Start background health updater
_updater_thread = threading.Thread(target=update_health_cache, daemon=True)
_updater_thread.start()


@app.route('/api/health', methods=['GET', 'HEAD', 'OPTIONS'])
def get_health_status():
    """
    Get health status for all LLM models (cached for fast response)
    
    Returns:
        JSON with model health data
        
    Example Response:
        {
            "timestamp": "2025-11-18T12:30:00Z",
            "total_models": 6,
            "healthy_models": 2,
            "models": [
                {
                    "name": "Llama-1B-Speed",
                    "endpoint": "http://localhost:8003/v1",
                    "backend": "vllm",
                    "is_healthy": true,
                    "response_time_ms": 150,
                    "consecutive_failures": 0,
                    "last_error": null,
                    "capabilities": ["chat", "fast"],
                    "vram_gb": 2.3,
                    "tokens_per_sec": 178
                },
                ...
            ]
        }
    """
    try:
        # Return cached data for fast response
        with _cache_lock:
            if _health_cache and _last_update and (time.time() - _last_update) < 30:
                # Cache is fresh
                return jsonify(_health_cache)
        
        # No cache or stale - return empty but valid response
        logger.warning("Health cache not ready, returning placeholder")
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'total_models': 0,
            'healthy_models': 0,
            'unhealthy_models': 0,
            'models': [],
            'cache_status': 'initializing'
        })
        
    except Exception as e:
        logger.error(f"Error in get_health_status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/summary', methods=['GET'])
def get_health_summary():
    """
    Get condensed health summary
    
    Returns:
        JSON with summary stats only
        
    Example Response:
        {
            "vllm": {
                "healthy": 1,
                "total": 5,
                "status": "degraded"
            },
            "ollama": {
                "healthy": 1,
                "total": 1,
                "status": "healthy"
            },
            "overall": {
                "healthy": 2,
                "total": 6,
                "status": "degraded"
            }
        }
    """
    try:
        client = get_client()
        health_status = client.check_all_health(force=True)
        
        vllm_models = [m for m in client.MODELS if m.backend == 'vllm']
        ollama_models = [m for m in client.MODELS if m.backend == 'ollama']
        
        vllm_healthy = sum(1 for m in vllm_models if health_status.get(m.name, None) and health_status[m.name].is_healthy)
        ollama_healthy = sum(1 for m in ollama_models if health_status.get(m.name, None) and health_status[m.name].is_healthy)
        
        total_healthy = vllm_healthy + ollama_healthy
        total_models = len(client.MODELS)
        
        def get_status(healthy, total):
            if healthy == total:
                return "healthy"
            elif healthy > 0:
                return "degraded"
            else:
                return "down"
        
        return jsonify({
            'vllm': {
                'healthy': vllm_healthy,
                'total': len(vllm_models),
                'status': get_status(vllm_healthy, len(vllm_models))
            },
            'ollama': {
                'healthy': ollama_healthy,
                'total': len(ollama_models),
                'status': get_status(ollama_healthy, len(ollama_models))
            },
            'overall': {
                'healthy': total_healthy,
                'total': total_models,
                'status': get_status(total_healthy, total_models)
            }
        })
    
    except Exception as e:
        logger.error(f"Summary check failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/ping', methods=['GET'])
def ping():
    """Simple health check for the API itself"""
    return jsonify({'status': 'ok', 'service': 'goodq4all-health-api'})


if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 Starting GoodQ4All Model Health Status API")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Endpoints:")
    logger.info("  http://localhost:5050/api/health         - Full health data")
    logger.info("  http://localhost:5050/api/health/summary - Summary only")
    logger.info("  http://localhost:5050/api/ping           - API health check")
    logger.info("")
    logger.info("=" * 70)
    
    app.run(
        host='0.0.0.0',
        port=5050,
        debug=False,  # Set to True for development
        threaded=True
    )
