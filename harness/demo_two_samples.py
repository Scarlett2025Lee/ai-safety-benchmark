#!/usr/bin/env python3
"""demo_two_samples.py — the smallest possible REAL run, for understanding.

Sends just 2 samples to a real model and prints, for each:
  the text -> the prompt sent -> the model's answer -> gold -> correct?
Then a 2-sample mini-scoreboard. Costs ~2 API calls (fractions of a cent).

Run:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...        # (PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-...")
    python demo_two_samples.py                 # uses a default model
    python demo_two_samples.py --model claude-haiku-4-5-20251001   # cheaper/faster

This is a learning aid. For the full benchmark use run_benchmark.py.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safetybench.data import load_samples
from safetybench.prompts import load_taxonomy, build_prompt
from safetybench.models import AnthropicRunner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-4-5")
    ap.add_argument("--config", default="zero_shot_policy")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("!! Set ANTHROPIC_API_KEY first. See the docstring at the top of this file.")
        sys.exit(1)

    tax = load_taxonomy(os.path.join(os.path.dirname(__file__), "..", "taxonomy.json"))
    samples = load_samples(os.path.join(os.path.dirname(__file__), "..", "data"))
    picks = [s for s in samples if s.id in ("HAR-EN-VIO-001", "HAR-ZH-ADV-001")]

    runner = AnthropicRunner(model=args.model)
    print(f"Model under test: {runner.name}   |   prompt config: {args.config}\n")

    correct = 0
    for s in picks:
        msgs = build_prompt(args.config, s.text, tax)
        pred = runner.classify(msgs)              # <-- the real API call
        ok = pred["severity"] == s.gold_severity
        correct += ok
        print("="*66)
        print(f"TEXT      : {s.text}")
        print(f"(lang={s.lang}, stratum={s.stratum})")
        print(f"MODEL SAID: {pred['severity']}  — {pred.get('rationale','')}")
        print(f"GOLD KEY  : {s.gold_severity}")
        print(f"RESULT    : {'CORRECT ✓' if ok else 'WRONG ✗ (this is a miss)'}")
        print()
    print("="*66)
    print(f"Mini-scoreboard: {correct}/{len(picks)} correct "
          f"({correct/len(picks)*100:.0f}% on these 2 samples)")
    print("Now scale this to all 600 with:  python run_benchmark.py --runner anthropic "
          f"--model {args.model} --config structured_rubric --out results/")


if __name__ == "__main__":
    main()
