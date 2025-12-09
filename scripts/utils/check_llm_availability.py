#!/usr/bin/env python3
"""
GoodQ LLM Availability Checker
Tests all configured LLM endpoints and reports availability
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Add project to path
sys.path.insert(0, str(Path(__file__).parents[1]))

try:
    from lib.goodq_logger import get_goodq_logger, MissionColors
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    MissionColors = None

class LLMChecker:
    """Check availability of LLM services"""
    
    LLM_ENDPOINTS = {
        'lmstudio': {
            'name': 'LM Studio',
            'url': 'http://localhost:1234/v1/models',
            'chat_url': 'http://localhost:1234/v1/chat/completions',
            'port': 1234,
            'priority': 1,
            'required': True,
        },
        'ollama': {
            'name': 'Ollama',
            'url': 'http://localhost:31434/api/tags',
            'chat_url': 'http://localhost:31434/api/generate',
            'port': 31434,
            'priority': 2,
            'required': False,
        },
        'openai': {
            'name': 'OpenAI API',
            'url': 'https://api.openai.com/v1/models',
            'chat_url': 'https://api.openai.com/v1/chat/completions',
            'env_var': 'OPENAI_API_KEY',
            'priority': 3,
            'required': False,
        }
    }
    
    def __init__(self):
        if LOGGER_AVAILABLE:
            self.logger = get_goodq_logger(__name__, component='Q Branch Comms')
        else:
            self.logger = None
        self.results = {}
    
    def _log(self, msg: str, level: str = 'info'):
        """Log message"""
        if self.logger:
            getattr(self.logger, level)(msg)
        else:
            print(f"[{level.upper()}] {msg}")
    
    def check_lmstudio(self) -> Dict:
        """Check LM Studio availability"""
        config = self.LLM_ENDPOINTS['lmstudio']
        self._log(f"Checking {config['name']}...", 'info')
        
        result = {
            'provider': 'lmstudio',
            'name': config['name'],
            'available': False,
            'url': config['url'],
            'status': 'unknown',
            'models': [],
            'error': None
        }
        
        if not REQUESTS_AVAILABLE:
            result['status'] = 'no_requests_library'
            result['error'] = 'requests library not available'
            return result
        
        try:
            response = requests.get(config['url'], timeout=3)
            if response.status_code == 200:
                result['available'] = True
                result['status'] = 'online'
                
                # Try to get models list
                try:
                    data = response.json()
                    if 'data' in data:
                        result['models'] = [m.get('id', 'unknown') for m in data['data']]
                except:
                    pass
                
                self._log(f"{config['name']}: ONLINE", 'info')
                if result['models']:
                    self._log(f"Models available: {', '.join(result['models'][:3])}", 'info')
            else:
                result['status'] = f'http_{response.status_code}'
                result['error'] = f'HTTP {response.status_code}'
                
        except requests.exceptions.ConnectionError:
            result['status'] = 'not_running'
            result['error'] = 'Connection refused - LM Studio not running or API server not started'
            self._log(f"{config['name']}: NOT RUNNING", 'warning')
            
        except requests.exceptions.Timeout:
            result['status'] = 'timeout'
            result['error'] = 'Request timeout'
            self._log(f"{config['name']}: TIMEOUT", 'warning')
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self._log(f"{config['name']}: ERROR - {e}", 'error')
        
        return result
    
    def check_ollama(self) -> Dict:
        """Check Ollama availability"""
        config = self.LLM_ENDPOINTS['ollama']
        self._log(f"Checking {config['name']}...", 'info')
        
        result = {
            'provider': 'ollama',
            'name': config['name'],
            'available': False,
            'url': config['url'],
            'status': 'unknown',
            'models': [],
            'error': None
        }
        
        if not REQUESTS_AVAILABLE:
            result['status'] = 'no_requests_library'
            result['error'] = 'requests library not available'
            return result
        
        try:
            response = requests.get(config['url'], timeout=3)
            if response.status_code == 200:
                result['available'] = True
                result['status'] = 'online'
                
                # Try to get models list
                try:
                    data = response.json()
                    if 'models' in data:
                        result['models'] = [m.get('name', 'unknown') for m in data['models']]
                except:
                    pass
                
                self._log(f"{config['name']}: ONLINE", 'info')
                if result['models']:
                    self._log(f"Models available: {', '.join(result['models'][:3])}", 'info')
            else:
                result['status'] = f'http_{response.status_code}'
                result['error'] = f'HTTP {response.status_code}'
                
        except requests.exceptions.ConnectionError:
            result['status'] = 'not_running'
            result['error'] = 'Connection refused - Ollama service not running'
            self._log(f"{config['name']}: NOT RUNNING", 'warning')
            
        except requests.exceptions.Timeout:
            result['status'] = 'timeout'
            result['error'] = 'Request timeout'
            self._log(f"{config['name']}: TIMEOUT", 'warning')
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self._log(f"{config['name']}: ERROR - {e}", 'error')
        
        return result
    
    def check_openai(self) -> Dict:
        """Check OpenAI API configuration"""
        config = self.LLM_ENDPOINTS['openai']
        self._log(f"Checking {config['name']}...", 'info')
        
        result = {
            'provider': 'openai',
            'name': config['name'],
            'available': False,
            'url': 'cloud',
            'status': 'unknown',
            'models': [],
            'error': None
        }
        
        # Check for API key
        api_key = os.environ.get(config['env_var'])
        if not api_key:
            # Try loading from .env.local
            env_file = Path(__file__).parents[1] / '.env.local'
            if env_file.exists():
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith(config['env_var']):
                            api_key = line.split('=', 1)[1].strip()
                            break
        
        if api_key:
            result['available'] = True
            result['status'] = 'configured'
            self._log(f"{config['name']}: API KEY CONFIGURED", 'info')
            self._log(f"Key: {api_key[:10]}...", 'debug')
        else:
            result['status'] = 'not_configured'
            result['error'] = f'{config["env_var"]} not set'
            self._log(f"{config['name']}: NOT CONFIGURED", 'warning')
        
        return result
    
    def check_all(self) -> Dict:
        """Check all LLM providers"""
        self._log("LLM Availability Check", 'info')
        
        results = {
            'lmstudio': self.check_lmstudio(),
            'ollama': self.check_ollama(),
            'openai': self.check_openai(),
        }
        
        # Determine which provider to use
        active_provider = None
        for provider in ['lmstudio', 'ollama', 'openai']:
            if results[provider]['available']:
                active_provider = provider
                break
        
        return {
            'providers': results,
            'active': active_provider,
            'timestamp': __import__('datetime').datetime.now().isoformat(),
        }
    
    def print_summary(self, results: Dict):
        """Print summary of results"""
        if LOGGER_AVAILABLE and MissionColors:
            print(f"\n{MissionColors.BOLD}{'='*70}{MissionColors.END}")
            print(f"{MissionColors.BOLD}LLM Availability Summary{MissionColors.END}")
            print(f"{MissionColors.BOLD}{'='*70}{MissionColors.END}\n")
        else:
            print("\n" + "="*70)
            print("LLM Availability Summary")
            print("="*70 + "\n")
        
        for provider_id, result in results['providers'].items():
            name = result['name']
            available = result['available']
            status = result['status']
            
            if LOGGER_AVAILABLE and MissionColors:
                color = MissionColors.SUCCESS if available else MissionColors.WARNING
                symbol = "✓" if available else "✗"
                print(f"{color}{symbol} {name:15s} - {status.upper()}{MissionColors.END}")
            else:
                symbol = "[OK]" if available else "[--]"
                print(f"{symbol} {name:15s} - {status.upper()}")
            
            if result.get('models'):
                print(f"  Models: {', '.join(result['models'][:3])}")
            
            if result.get('error'):
                print(f"  Error: {result['error']}")
        
        print()
        
        active = results.get('active')
        if active:
            active_name = results['providers'][active]['name']
            if LOGGER_AVAILABLE and MissionColors:
                print(f"{MissionColors.SUCCESS}Active LLM Provider: {active_name}{MissionColors.END}")
            else:
                print(f"Active LLM Provider: {active_name}")
        else:
            if LOGGER_AVAILABLE and MissionColors:
                print(f"{MissionColors.ERROR}No LLM provider available{MissionColors.END}")
            else:
                print("No LLM provider available")
        
        print()


def main():
    """Main entry point"""
    checker = LLMChecker()
    results = checker.check_all()
    checker.print_summary(results)
    
    # Return appropriate exit code
    if results['active']:
        return 0  # Success
    else:
        return 1  # No provider available


if __name__ == '__main__':
    sys.exit(main())
