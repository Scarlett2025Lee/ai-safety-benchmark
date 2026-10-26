#!/usr/bin/env python3
"""Run the safety benchmark end-to-end.

Examples
--------
# Runs with the built-in mock model (no API key, no network):
python run_benchmark.py --runner mock --config structured_rubric

# All three prompt configs with the mock model, write reports:
python run_benchmark.py --runner mock --config all --out results/

# Real model (requires ANTHROPIC_API_KEY and `pip install anthropic`):
python run_benchmark.py --runner anthropic --model claude-sonnet-4-5 --config structured_rubric
"""
from __future__ import annotations
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from safetybench.data import load_samples, expand_all, DEFAULT_IDENTITIES
from safetybench.prompts import load_taxonomy, build_prompt, PROMPT_CONFIGS
from safetybench.models import get_runner
from safetybench.metrics import compute, bootstrap_ci, slice_metrics


def evaluate(samples, taxonomy, runner_kind, config, model):
    runner = get_runner(runner_kind, config_hint=config, model=model)
    rows = []
    for s in samples:
        messages = build_prompt(config, s.text, taxonomy)
        if runner_kind == "mock":
            # The mock simulator needs a hidden control channel to know the gold
            # label + slice. A REAL runner never receives this — it only ever
            # sees the policy prompt and the content. This keeps the mock demoable
            # while ensuring real evaluations are untainted.
            ctrl = (f"\n<<GOLD:{s.gold_severity}|stratum={s.stratum}"
                    f"|lang={s.lang}>>")
            messages = [dict(m) for m in messages]
            messages[-1]["content"] += ctrl
        pred = runner.classify(messages)
        rows.append({
            "id": s.id, "gold": s.gold_severity, "pred": pred["severity"],
            "lang": s.lang, "category": s.category, "stratum": s.stratum,
            "adversarial_pattern": s.adversarial_pattern,
            "gold_severity": s.gold_severity,
        })
    return runner.name, rows


def report(rows, config, runner_name):
    golds = [r["gold"] for r in rows]
    preds = [r["pred"] for r in rows]
    overall = compute(golds, preds)

    out = {
        "runner": runner_name,
        "prompt_config": config,
        "n": overall.n,
        "overall": overall.as_dict(),
        "overall_ci": {
            "macro_f1": bootstrap_ci(golds, preds, "macro_f1"),
            "fnr": bootstrap_ci(golds, preds, "fnr"),
            "binary_recall": bootstrap_ci(golds, preds, "binary_recall"),
        },
        "by_language": {},
        "by_category": {},
        "by_stratum": {},
        "by_adversarial_pattern": {},
    }
    for by, dest in (("lang", "by_language"), ("category", "by_category"),
                     ("stratum", "by_stratum"),
                     ("adversarial_pattern", "by_adversarial_pattern")):
        for key, m in slice_metrics(rows, by).items():
            out[dest][key] = m.as_dict()
    return out


def print_summary(rep):
    o = rep["overall"]
    ci = rep["overall_ci"]
    print(f"\n=== {rep['runner']}  |  prompt={rep['prompt_config']}  |  n={rep['n']} ===")
    print(f"  exact severity accuracy : {o['exact_accuracy']:.3f}")
    print(f"  within-one-tier         : {o['within_one_tier']:.3f}")
    print(f"  macro-F1 (4-class)      : {o['macro_f1']:.3f}  "
          f"95% CI [{ci['macro_f1'][0]:.3f}, {ci['macro_f1'][1]:.3f}]")
    print(f"  binary recall (actioned): {o['binary_recall']:.3f}  "
          f"95% CI [{ci['binary_recall'][0]:.3f}, {ci['binary_recall'][1]:.3f}]")
    print(f"  FNR (safety misses)     : {o['fnr']:.3f}  "
          f"95% CI [{ci['fnr'][0]:.3f}, {ci['fnr'][1]:.3f}]")
    print(f"  over-removal (gold S0)  : {o['over_removal']:.3f}")
    print("  by language:")
    for k, m in rep["by_language"].items():
        print(f"    {k}: macro-F1={m['macro_f1']:.3f}  FNR={m['fnr']:.3f}")
    print("  by stratum:")
    for k, m in rep["by_stratum"].items():
        print(f"    {k:12s}: macro-F1={m['macro_f1']:.3f}  FNR={m['fnr']:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
    ap.add_argument("--taxonomy", default=os.path.join(HERE, "..", "taxonomy.json"))
    ap.add_argument("--runner", default="mock", choices=["mock", "anthropic"])
    ap.add_argument("--model", default="claude-sonnet-4-5")
    ap.add_argument("--config", default="structured_rubric",
                    choices=PROMPT_CONFIGS + ["all"])
    ap.add_argument("--out", default=None, help="dir to write JSON reports")
    ap.add_argument("--limit", type=int, default=0, help="cap samples (debug)")
    args = ap.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)
    base = load_samples(args.data)
    samples = expand_all(base, DEFAULT_IDENTITIES)
    if args.limit:
        samples = samples[:args.limit]
    print(f"loaded {len(base)} base samples -> {len(samples)} after placeholder expansion")

    configs = PROMPT_CONFIGS if args.config == "all" else [args.config]
    all_reps = []
    for cfg in configs:
        runner_name, rows = evaluate(samples, taxonomy, args.runner, cfg, args.model)
        rep = report(rows, cfg, runner_name)
        print_summary(rep)
        all_reps.append(rep)
        if args.out:
            os.makedirs(args.out, exist_ok=True)
            fn = os.path.join(args.out, f"report_{runner_name}_{cfg}.json")
            with open(fn, "w", encoding="utf-8") as f:
                json.dump({"report": rep, "rows": rows}, f, ensure_ascii=False, indent=2)
            print(f"  wrote {fn}")

    if args.out and len(all_reps) > 1:
        cmp_fn = os.path.join(args.out, "compare_configs.json")
        with open(cmp_fn, "w", encoding="utf-8") as f:
            json.dump([{"config": r["prompt_config"], "overall": r["overall"]}
                       for r in all_reps], f, ensure_ascii=False, indent=2)
        print(f"\nwrote comparison -> {cmp_fn}")


if __name__ == "__main__":
    main()
