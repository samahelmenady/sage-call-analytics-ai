"""
Benchmark runner for comparing GenAI providers/models on:
  - Schema validity rate
  - Sentiment, category, priority, and resolution accuracy
  - End-to-end latency (p50 / p95)

Usage:
    python benchmarks/run_benchmark.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Ensure project root is on sys.path when invoked as `python benchmarks/run_benchmark.py`
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.services.genai.cohere_genai import CohereGenAIProvider
from backend.services.genai.gemini_genai import GeminiGenAIProvider
from backend.services.genai.interface import GenAIProvider


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return round(ordered[idx], 1)


def _build_provider(provider_type: str, model: str) -> GenAIProvider:
    if provider_type == "gemini":
        return GeminiGenAIProvider(model=model)
    if provider_type == "cohere":
        return CohereGenAIProvider(model=model)
    raise ValueError(f"Unsupported benchmark provider: {provider_type}")


async def evaluate_provider(name: str, provider_type: str, model: str, dataset: list[dict]) -> dict:
    provider = _build_provider(provider_type, model)
    latencies: list[float] = []
    valid_count = 0
    sent_ok = cat_ok = prio_ok = res_ok = 0

    for item in dataset:
        t0 = time.perf_counter()
        try:
            res = await provider.analyze_transcript(
                transcript=item["transcript"],
                call_id=item["call_id"],
                language=item.get("language", "ar"),
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)
            valid_count += 1

            gt = item["ground_truth"]
            if res.sentiment.overall == gt["sentiment"]:
                sent_ok += 1
            if res.problem.category == gt["category"]:
                cat_ok += 1
            if res.problem.priority == gt["priority"]:
                prio_ok += 1
            if res.resolution.resolved == gt["resolved"]:
                res_ok += 1
        except Exception:
            latencies.append((time.perf_counter() - t0) * 1000.0)

    n = max(1, len(dataset))
    return {
        "provider": name,
        "model": model,
        "dataset_size": len(dataset),
        "schema_validity_rate": round(valid_count / n, 3),
        "sentiment_accuracy": round(sent_ok / n, 3),
        "category_accuracy": round(cat_ok / n, 3),
        "priority_accuracy": round(prio_ok / n, 3),
        "resolution_accuracy": round(res_ok / n, 3),
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else 0.0,
        "latency_p95_ms": _percentile(latencies, 95),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Sage GenAI benchmark")
    parser.add_argument("--config", default="benchmarks/benchmark_config.yaml")
    parser.add_argument("--dataset", default="benchmarks/data/test_calls.json")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    out_dir = Path(cfg.get("output_dir", "results/benchmarks"))
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for entry in cfg.get("providers_to_compare", []):
        try:
            results[entry["name"]] = await evaluate_provider(
                entry["name"], entry["genai_provider"], entry["model"], dataset
            )
        except Exception as exc:
            results[entry["name"]] = {"error": str(exc)}

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report = {"timestamp": ts, "dataset_size": len(dataset), "results": results}
    json_path = out_dir / f"{ts}_benchmark_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Benchmark report saved to {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
