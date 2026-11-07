"""Benchmark an OpenAI-compatible LLM server before/after an upgrade.
Usage: python3 scripts/bench-llm.py --label before
"""
import argparse, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor; from statistics import median

PARAGRAPH = ("The quick brown fox jumps over the lazy dog. " * 10).strip()

def get_model(url):
    return json.load(urllib.request.urlopen(f"{url}/models", timeout=10))["data"][0]["id"]

def make_prompt(r, i, pt):
    target = max(0, pt * 4)
    filler = (PARAGRAPH + " ") * ((target + len(PARAGRAPH)) // len(PARAGRAPH)) if target else ""
    return f"Request #{r}-{i} ({time.time()}).\n{filler}\nSummarize the text above in detail."

def run_request(url, model, prompt, mt):
    start = time.time()
    try:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True,
                   "stream_options": {"include_usage": True}, "temperature": 0, "max_tokens": mt}
        req = urllib.request.Request(f"{url}/chat/completions", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        first, chunks, ct = None, 0, None
        with urllib.request.urlopen(req, timeout=600) as resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                if not data:
                    continue
                obj = json.loads(data)
                ch = obj.get("choices") or []
                if ch:
                    delta = ch[0].get("delta") or {}
                    if delta.get("content") or delta.get("reasoning_content"):
                        if first is None:
                            first = time.time()
                        chunks += 1
                usage = obj.get("usage")
                if usage and usage.get("completion_tokens") is not None:
                    ct = usage["completion_tokens"]
        tokens = ct if ct is not None else chunks
        end = time.time()
        return {"ok": True, "ttft": first - start if first else None,
                "decode": tokens / (end - first) if first and end > first else 0.0, "tokens": tokens}
    except Exception as e:
        return {"ok": False, "error": str(e), "tokens": 0}

def bench_level(url, model, c, runs, mt, pt, first_error):
    ttfts, decodes, aggs, errors = [], [], [], 0
    for r in range(runs):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=c) as ex:
            results = [f.result() for f in [ex.submit(run_request, url, model, make_prompt(r, i, pt), mt) for i in range(c)]]
        t1 = time.time()
        total = 0
        for res in results:
            if res["ok"]:
                if res["ttft"] is not None:
                    ttfts.append(res["ttft"])
                decodes.append(res["decode"])
                total += res["tokens"]
            else:
                errors += 1
                if first_error[0] is None:
                    first_error[0] = res.get("error", "unknown")
                    print(f"First error: {first_error[0]}")
        aggs.append(total / (t1 - t0) if t1 > t0 else 0.0)
    return {"ttft": median(ttfts) if ttfts else 0.0, "decode": median(decodes) if decodes else 0.0,
            "aggregate": median(aggs) if aggs else 0.0, "errors": errors}

def print_table(rows):
    h = f"{'Concurrency':>11} {'TTFT (s)':>10} {'Decode (tok/s)':>16} {'Aggregate (tok/s)':>18} {'Errors':>8}"
    print(h + "\n" + "-" * len(h))
    for c, m in rows:
        print(f"{c:>11} {m['ttft']:>10.3f} {m['decode']:>16.2f} {m['aggregate']:>18.2f} {m['errors']:>8}")

def save(rows, args, model):
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open("bench-llm.jsonl", "a", encoding="utf-8") as f:
        for c, m in rows:
            f.write(json.dumps({"label": args.label, "timestamp": ts, "url": args.url, "model": model,
                                "concurrency": c, "ttft_s": m["ttft"], "decode_tps": m["decode"],
                                "aggregate_tps": m["aggregate"], "errors": m["errors"],
                                "max_tokens": args.max_tokens, "prompt_tokens": args.prompt_tokens}) + "\n")

def main():
    p = argparse.ArgumentParser(description="Benchmark an OpenAI-compatible LLM server.")
    p.add_argument("--url", default="http://127.0.0.1:8000/v1")
    p.add_argument("--model", default=None)
    p.add_argument("--concurrency", default="1,4")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--max-tokens", type=int, default=512)
    p.add_argument("--prompt-tokens", type=int, default=2000)
    p.add_argument("--label", default="")
    args = p.parse_args()
    try:
        model = args.model or get_model(args.url)
    except Exception as e:
        print(f"Cannot determine model: {e}")
        return
    rows, first_error = [], [None]
    try:
        for c in [int(x) for x in args.concurrency.split(",") if x.strip()]:
            if c > 0:
                rows.append((c, bench_level(args.url, model, c, args.runs, args.max_tokens, args.prompt_tokens, first_error)))
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if rows:
            print_table(rows)
            save(rows, args, model)

if __name__ == "__main__":
    main()
