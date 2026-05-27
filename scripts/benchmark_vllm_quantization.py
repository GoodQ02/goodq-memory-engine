#!/usr/bin/env python3
"""
GoodQ4All vLLM A/B Quantization Benchmarking Tool
==================================================
Measures TTFT, throughput (tokens/sec), generation accuracy, and GPU VRAM 
consumption across different vLLM KV-cache configurations.
"""

import sys
import os
import time
import json
import argparse
import subprocess
import requests

# Representative test prompts
TEST_PROMPTS = [
    {
        "name": "Short Query",
        "messages": [
            {"role": "user", "content": "Explain the concept of quantum computing in one simple sentence."}
        ],
        "max_tokens": 50
    },
    {
        "name": "Structured JSON Extraction",
        "messages": [
            {"role": "system", "content": "You are a precise data extractor. Extract the entities mentioned in the text and format them strictly as JSON: {\"people\": [...], \"locations\": [...]}"},
            {"role": "user", "content": "Yesterday, Jerry and George met at Monk's Cafe in New York City to discuss their new pilot script. Later, Elaine arrived with Kramer."}
        ],
        "max_tokens": 150
    },
    {
        "name": "Long Context Reasoning",
        "messages": [
            {"role": "system", "content": "Summarize the scene and identify the emotional tone of the dialogue."},
            {"role": "user", "content": "Jerry: I don't want to go to the party.\nGeorge: You have to go. Everyone expects us.\nJerry: Why? What is the point of a party? You stand around, you eat chips, you make small talk with people you don't even like.\nGeorge: That is the whole definition of society! We are a society, Jerry! We have to make small talk!\nJerry: I'm not a society. I'm a person. I like to sit on my couch and watch TV.\nGeorge: Sienfeld, you are missing the bigger picture. Katy and Katy's dogs, Lovie and Ryder, will be there. We have to support them!\nElaine: (entering) Hey. Did you hear? The party got moved. It's at Monk's now.\nJerry: monk's? That's even worse. Now I have to pay for my own chips.\nKramer: (sliding in) Yo! You guys ready? Giddyup!"}
        ],
        "max_tokens": 200
    }
]

def query_gpu_vram() -> float:
    """Queries nvidia-smi inside WSL to find active GPU VRAM in GB."""
    try:
        if sys.platform == "win32":
            cmd = "wsl -d Ubuntu-22.04 -- nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"
        else:
            cmd = "nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits"
            
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            val = float(res.stdout.strip().splitlines()[0])
            return val / 1024.0 # Convert MB to GB
    except Exception:
        pass
    return 0.0

def run_benchmark(endpoint: str, model_id: str, test_run_name: str) -> dict:
    results = []
    
    # 0. Initial VRAM check
    vram_start = query_gpu_vram()
    print(f"\n[RUN] Starting Benchmark: {test_run_name}")
    print(f"[VRAM] Baseline GPU VRAM: {vram_start:.2f} GB")
    
    headers = {"Content-Type": "application/json"}
    
    for prompt in TEST_PROMPTS:
        print(f"\n---> Prompt: {prompt['name']}")
        payload = {
            "model": model_id,
            "messages": prompt["messages"],
            "max_tokens": prompt["max_tokens"],
            "temperature": 0.0, # Keep deterministic
            "stream": True
        }
        
        start_time = time.time()
        ttft = None
        first_chunk = True
        generated_text = ""
        chunks_count = 0
        
        try:
            response = requests.post(
                f"{endpoint}/chat/completions",
                json=payload,
                headers=headers,
                stream=True,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"[FAIL] HTTP error {response.status_code}: {response.text}")
                continue
                
            for line in response.iter_lines():
                if not line:
                    continue
                line_text = line.decode("utf-8").strip()
                if not line_text.startswith("data: "):
                    continue
                data_str = line_text[6:]
                if data_str == "[DONE]":
                    break
                    
                try:
                    chunk_data = json.loads(data_str)
                except Exception:
                    continue
                    
                if first_chunk:
                    ttft = (time.time() - start_time) * 1000.0 # ms
                    first_chunk = False
                    
                if "choices" in chunk_data and chunk_data["choices"]:
                    delta = chunk_data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        generated_text += content
                        chunks_count += 1
                        
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Count tokens (approximate as chunk count)
            tokens_generated = chunks_count
            throughput = tokens_generated / total_duration if total_duration > 0 else 0.0
            
            # Check JSON validity if structured extraction
            json_valid = "N/A"
            if prompt["name"] == "Structured JSON Extraction":
                try:
                    clean_text = generated_text.strip()
                    if clean_text.startswith("```json"):
                        clean_text = clean_text[7:]
                    if clean_text.endswith("```"):
                        clean_text = clean_text[:-3]
                    json.loads(clean_text.strip())
                    json_valid = "PASS"
                except Exception:
                    json_valid = "FAIL"
            
            vram_end = query_gpu_vram()
            
            print(f"     TTFT: {ttft:.1f} ms" if ttft else "     TTFT: N/A")
            print(f"     Throughput: {throughput:.1f} tok/sec")
            print(f"     Tokens: {tokens_generated}")
            if json_valid != "N/A":
                print(f"     JSON Check: {json_valid}")
            print(f"     Active GPU VRAM: {vram_end:.2f} GB")
            
            results.append({
                "prompt_name": prompt["name"],
                "ttft_ms": ttft,
                "throughput_tok_sec": throughput,
                "total_duration_sec": total_duration,
                "tokens_generated": tokens_generated,
                "json_valid": json_valid,
                "output_preview": generated_text[:120].replace('\n', ' '),
                "gpu_vram_gb": vram_end
            })
            
        except Exception as e:
            print(f"[FAIL] Error running prompt: {e}")
            
    vram_peak = query_gpu_vram()
    print(f"\n[RUN COMPLETE] Peak VRAM: {vram_peak:.2f} GB")
    
    return {
        "run_name": test_run_name,
        "model_id": model_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vram_baseline_gb": vram_start,
        "vram_peak_gb": vram_peak,
        "results": results
    }

def print_markdown_comparison(reports_dir: str):
    """Generates and prints a comparison Markdown table of all runs in the reports dir."""
    files = [f for f in os.listdir(reports_dir) if f.startswith("vllm_benchmark_") and f.endswith(".json")]
    if not files:
        print("[INFO] No benchmark files found to compare.")
        return
        
    runs = []
    for f in sorted(files):
        with open(os.path.join(reports_dir, f), "r") as fh:
            try:
                runs.append(json.load(fh))
            except Exception:
                pass
                
    if not runs:
        return
        
    print("\n" + "=" * 80)
    print("                      A/B QUANTIZATION BENCHMARK SUMMARY")
    print("=" * 80)
    
    # Header
    print(f"| Run Name | Peak VRAM (GB) | Prompt | TTFT (ms) | Speed (tok/s) | JSON Validation |")
    print(f"| :--- | :---: | :--- | :---: | :---: | :---: |")
    
    for run in runs:
        name = run["run_name"]
        peak_vram = f"{run['vram_peak_gb']:.2f}"
        for idx, res in enumerate(run["results"]):
            ttft = f"{res['ttft_ms']:.1f}" if res['ttft_ms'] else "N/A"
            speed = f"{res['throughput_tok_sec']:.1f}"
            json_chk = res["json_valid"]
            
            # Print run details (grouping name/vram on first row)
            row_name = name if idx == 0 else ""
            row_vram = peak_vram if idx == 0 else ""
            print(f"| {row_name:25} | {row_vram:14} | {res['prompt_name']:30} | {ttft:9} | {speed:13} | {json_chk:15} |")
        print(f"| " + "-" * 25 + " | " + "-" * 14 + " | " + "-" * 30 + " | " + "-" * 9 + " | " + "-" * 13 + " | " + "-" * 15 + " |")

def main():
    parser = argparse.ArgumentParser(description="vLLM A/B Quantization Benchmarker")
    parser.add_argument("--endpoint", default="http://127.0.0.1:38005/v1", help="vLLM REST endpoint")
    parser.add_argument("--run-name", required=True, help="Descriptive name for this A/B run (e.g. baseline-fp8, turboquant-3bit)")
    parser.add_argument("--compare-only", action="store_true", help="Print summary of existing logs without running benchmark")
    args = parser.parse_args()
    
    # Locate reports dir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    reports_dir = os.path.join(project_root, "reports", "local_housekeeping")
    os.makedirs(reports_dir, exist_ok=True)
    
    if args.compare_only:
        print_markdown_comparison(reports_dir)
        return
        
    # Get active model ID
    try:
        res = requests.get(f"{args.endpoint}/models", timeout=5)
        if res.status_code != 200:
            print(f"[ERROR] Could not connect to vLLM on {args.endpoint}: HTTP {res.status_code}")
            sys.exit(1)
        model_id = res.json()["data"][0]["id"]
    except Exception as e:
        print(f"[ERROR] Could not connect to vLLM on {args.endpoint}: {e}")
        sys.exit(1)
        
    # Run
    report = run_benchmark(args.endpoint, model_id, args.run_name)
    
    # Save log
    filename = f"vllm_benchmark_{args.run_name.lower().replace(' ', '_').replace('-', '_')}_{int(time.time())}.json"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\n[OK] Benchmark saved to {filepath}")
    
    # Compare
    print_markdown_comparison(reports_dir)

if __name__ == "__main__":
    main()
