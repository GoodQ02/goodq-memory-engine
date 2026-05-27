#!/usr/bin/env python3
"""
Scientific vLLM Quantization Benchmarking Tool
==============================================
Runs multiple warm and cold iterations to calculate p50/p95 TTFT,
mean throughput, peak VRAM, and JSON validation failure rates.
"""

import sys
import os
import time
import json
import math
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

def percentile(data, percent):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (percent / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1

def run_warmup(endpoint: str, model_id: str):
    print("[WARMUP] Sending initial query to warm up the model and compile graphs...")
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 5,
        "temperature": 0.0,
        "stream": False
    }
    try:
        requests.post(f"{endpoint}/chat/completions", json=payload, headers=headers, timeout=60)
        print("[WARMUP] Completed.")
    except Exception as e:
        print(f"[WARMUP] Failed: {e}")

def run_scientific_benchmark(endpoint: str, model_id: str, test_run_name: str, iterations: int) -> dict:
    run_warmup(endpoint, model_id)
    
    vram_start = query_gpu_vram()
    print(f"\n[RUN] Starting Scientific Benchmark: {test_run_name}")
    print(f"[VRAM] Baseline GPU VRAM: {vram_start:.2f} GB")
    
    headers = {"Content-Type": "application/json"}
    prompt_summaries = []
    
    for prompt in TEST_PROMPTS:
        print(f"\n---> Prompt: {prompt['name']} (running {iterations} iterations)")
        ttft_list = []
        throughput_list = []
        json_failures = 0
        
        payload = {
            "model": model_id,
            "messages": prompt["messages"],
            "max_tokens": prompt["max_tokens"],
            "temperature": 0.0, # Keep deterministic
            "stream": True
        }
        
        for i in range(iterations):
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
                    print(f"  [FAIL] Iteration {i+1} got HTTP {response.status_code}")
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
                
                if ttft is not None:
                    ttft_list.append(ttft)
                
                throughput = chunks_count / total_duration if total_duration > 0 else 0.0
                throughput_list.append(throughput)
                
                # JSON check if structured extraction
                if prompt["name"] == "Structured JSON Extraction":
                    try:
                        clean_text = generated_text.strip()
                        if clean_text.startswith("```json"):
                            clean_text = clean_text[7:]
                        if clean_text.endswith("```"):
                            clean_text = clean_text[:-3]
                        json.loads(clean_text.strip())
                    except Exception:
                        json_failures += 1
                        
            except Exception as e:
                print(f"  [FAIL] Iteration {i+1} error: {e}")
                
        # Calculate stats
        p50_ttft = percentile(ttft_list, 50.0)
        p95_ttft = percentile(ttft_list, 95.0)
        mean_throughput = sum(throughput_list) / len(throughput_list) if throughput_list else 0.0
        json_failure_rate = (json_failures / iterations) * 100.0 if prompt["name"] == "Structured JSON Extraction" else 0.0
        
        vram_end = query_gpu_vram()
        print(f"     p50 TTFT: {p50_ttft:.1f} ms | p95 TTFT: {p95_ttft:.1f} ms")
        print(f"     Mean Throughput: {mean_throughput:.1f} tok/sec")
        if prompt["name"] == "Structured JSON Extraction":
            print(f"     JSON Failure Rate: {json_failure_rate:.1f}%")
        print(f"     Active GPU VRAM: {vram_end:.2f} GB")
        
        prompt_summaries.append({
            "prompt_name": prompt["name"],
            "p50_ttft_ms": p50_ttft,
            "p95_ttft_ms": p95_ttft,
            "mean_throughput_tok_sec": mean_throughput,
            "json_failure_rate": json_failure_rate,
            "gpu_vram_gb": vram_end
        })
        
    vram_peak = query_gpu_vram()
    print(f"\n[RUN COMPLETE] Peak VRAM: {vram_peak:.2f} GB")
    
    return {
        "run_name": test_run_name,
        "model_id": model_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "vram_baseline_gb": vram_start,
        "vram_peak_gb": vram_peak,
        "iterations": iterations,
        "prompts": prompt_summaries
    }

def print_scientific_comparison(reports_dir: str):
    files = [f for f in os.listdir(reports_dir) if f.startswith("scientific_benchmark_") and f.endswith(".json")]
    if not files:
        print("[INFO] No scientific benchmark files found to compare.")
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
        
    print("\n" + "=" * 100)
    print("                    SCIENTIFIC QUANTIZATION BENCHMARK SUMMARY")
    print("=" * 100)
    
    print(f"| Run Name | Peak VRAM | Prompt | p50 TTFT (ms) | p95 TTFT (ms) | Speed (tok/s) | JSON Fail Rate |")
    print(f"| :--- | :---: | :--- | :---: | :---: | :---: | :---: |")
    
    for run in runs:
        name = run["run_name"]
        peak_vram = f"{run['vram_peak_gb']:.2f} GB"
        for idx, res in enumerate(run["prompts"]):
            p50 = f"{res['p50_ttft_ms']:.1f}"
            p95 = f"{res['p95_ttft_ms']:.1f}"
            speed = f"{res['mean_throughput_tok_sec']:.1f}"
            json_fail = f"{res['json_failure_rate']:.1f}%" if res['prompt_name'] == "Structured JSON Extraction" else "N/A"
            
            row_name = name if idx == 0 else ""
            row_vram = peak_vram if idx == 0 else ""
            print(f"| {row_name:25} | {row_vram:9} | {res['prompt_name']:30} | {p50:13} | {p95:13} | {speed:13} | {json_fail:14} |")
        print(f"| " + "-" * 25 + " | " + "-" * 9 + " | " + "-" * 30 + " | " + "-" * 13 + " | " + "-" * 13 + " | " + "-" * 13 + " | " + "-" * 14 + " |")

def main():
    parser = argparse.ArgumentParser(description="Scientific vLLM Quantization Benchmarker")
    parser.add_argument("--endpoint", default="http://127.0.0.1:38005/v1", help="vLLM REST endpoint")
    parser.add_argument("--run-name", required=True, help="Run name (e.g. v21-fp8, v21-turboquant)")
    parser.add_argument("--iterations", type=int, default=20, help="Number of benchmark iterations")
    parser.add_argument("--compare-only", action="store_true", help="Compare existing scientific runs only")
    args = parser.parse_args()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    reports_dir = os.path.join(project_root, "reports", "local_housekeeping")
    os.makedirs(reports_dir, exist_ok=True)
    
    if args.compare_only:
        print_scientific_comparison(reports_dir)
        return
        
    try:
        res = requests.get(f"{args.endpoint}/models", timeout=5)
        if res.status_code != 200:
            print(f"[ERROR] Could not connect to vLLM on {args.endpoint}: HTTP {res.status_code}")
            sys.exit(1)
        model_id = res.json()["data"][0]["id"]
    except Exception as e:
        print(f"[ERROR] Could not connect to vLLM on {args.endpoint}: {e}")
        sys.exit(1)
        
    report = run_scientific_benchmark(args.endpoint, model_id, args.run_name, args.iterations)
    
    filename = f"scientific_benchmark_{args.run_name.lower().replace(' ', '_').replace('-', '_')}_{int(time.time())}.json"
    filepath = os.path.join(reports_dir, filename)
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2)
        
    print(f"\n[OK] Scientific benchmark saved to {filepath}")
    print_scientific_comparison(reports_dir)

if __name__ == "__main__":
    main()
