"""
STT benchmarking utility using Word Error Rate (WER) and Character Error Rate (CER).

Usage:
    python benchmarks/stt_benchmark.py --reference "reference text" --hypothesis "transcribed text"
"""

from __future__ import annotations

import argparse

from jiwer import cer, wer


def compute_stt_metrics(reference: str, hypothesis: str) -> dict[str, float]:
    return {
        "wer": round(float(wer(reference, hypothesis)), 4),
        "cer": round(float(cer(reference, hypothesis)), 4),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute STT WER/CER metrics")
    parser.add_argument("--reference", required=True)
    parser.add_argument("--hypothesis", required=True)
    args = parser.parse_args()
    print(compute_stt_metrics(args.reference, args.hypothesis))
