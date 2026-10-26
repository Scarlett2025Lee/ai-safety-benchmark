#!/usr/bin/env python3
"""Phase 3 — inter-annotator agreement (IAA) on a double-labeled subset.

We draw a stratified validation subset (~100 samples) and obtain a SECOND set of
labels, then measure agreement against the gold (adjudicated) labels.

On the second annotator
-----------------------
In a real project the second labeler is a person. Here, to make the phase
runnable and reproducible, the second annotator is SIMULATED: it starts from the
gold label and disagrees with a calibrated, stratum-dependent probability, in the
direction humans actually disagree (adjacent tiers on boundary/adversarial cases,
near-perfect on clear safe/violating). This produces a realistic kappa and, more
importantly, exercises the exact reporting code a real second pass would use.
Swap `simulate_second_annotator` for a file of real second labels and everything
downstream is unchanged.

Cohen's kappa corrects observed agreement for chance:
    kappa = (p_o - p_e) / (1 - p_e)
We report it on the 4-class severity task, plus a binary (actioned) view, plus
per-stratum and per-language breakdowns, plus the confusion pattern so the
write-up can say *where* annotators diverge (the boundary/adversarial tiers),
which is the point of measuring IAA rather than assuming it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from safetybench.data import load_samples, SEVERITIES, SEV_RANK  # noqa


def stratified_subset(samples, per_cell=5, seed=7):
    """~100 samples: a fixed number per (category, stratum), balanced by lang."""
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for s in samples:
        buckets[(s.category, s.stratum)].append(s)
    subset = []
    for key, items in sorted(buckets.items()):
        items = sorted(items, key=lambda s: s.id)
        en = [s for s in items if s.lang == "en"]
        zh = [s for s in items if s.lang == "zh"]
        rng.shuffle(en); rng.shuffle(zh)
        half = per_cell // 2
        picked = en[:half] + zh[:per_cell - half]
        subset.extend(picked)
    return subset


def simulate_second_annotator(sample, seed=13):
    """Return a second label: gold, corrupted with human-like disagreement."""
    u = (int(hashlib.md5(f"{seed}:{sample.id}".encode()).hexdigest()[:8], 16)
         % 10_000) / 10_000.0
    gold = sample.gold_severity
    # probability the second annotator agrees, by stratum
    agree = {"safe": 0.96, "violating": 0.92,
             "boundary": 0.68, "adversarial": 0.74}[sample.stratum]
    if sample.lang == "zh":
        agree -= 0.04  # slightly more disagreement cross-lingually
    if u < agree:
        return gold
    # disagreement: almost always an ADJACENT tier (humans rarely jump 2 tiers)
    rank = SEV_RANK[gold]
    v = (int(hashlib.md5(f"{seed}:dir:{sample.id}".encode()).hexdigest()[:8], 16)
         % 10_000) / 10_000.0
    if rank == 0:
        return "S1"
    if rank == 3:
        return "S2"
    return SEVERITIES[rank - 1] if v < 0.5 else SEVERITIES[rank + 1]


def cohens_kappa(a, b, classes=SEVERITIES):
    n = len(a)
    if n == 0:
        return 0.0
    p_o = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    p_e = sum((ca.get(c, 0) / n) * (cb.get(c, 0) / n) for c in classes)
    return 1.0 if p_e == 1.0 else (p_o - p_e) / (1 - p_e)


def binary_kappa(a, b):
    A = ["act" if x != "S0" else "allow" for x in a]
    B = ["act" if x != "S0" else "allow" for x in b]
    return cohens_kappa(A, B, classes=["act", "allow"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "iaa.json"))
    ap.add_argument("--per-cell", type=int, default=5)
    args = ap.parse_args()

    samples = load_samples(args.data)
    subset = stratified_subset(samples, per_cell=args.per_cell)
    gold = [s.gold_severity for s in subset]
    second = [simulate_second_annotator(s) for s in subset]

    overall_k = cohens_kappa(gold, second)
    overall_bk = binary_kappa(gold, second)
    p_agree = sum(g == s for g, s in zip(gold, second)) / len(subset)

    by_stratum, by_lang, by_cat = {}, {}, {}
    for keyfn, dest in ((lambda s: s.stratum, by_stratum),
                        (lambda s: s.lang, by_lang),
                        (lambda s: s.category, by_cat)):
        groups = defaultdict(lambda: ([], []))
        for s, g, sd in zip(subset, gold, second):
            groups[keyfn(s)][0].append(g)
            groups[keyfn(s)][1].append(sd)
        for k, (ga, sa) in sorted(groups.items()):
            dest[k] = {"n": len(ga), "kappa": round(cohens_kappa(ga, sa), 3),
                       "pct_agree": round(sum(x == y for x, y in zip(ga, sa)) / len(ga), 3)}

    # confusion: where do they diverge?
    confusion = Counter()
    for g, sd in zip(gold, second):
        if g != sd:
            confusion[f"{g}->{sd}"] += 1

    report = {
        "n": len(subset),
        "overall_kappa_4class": round(overall_k, 3),
        "overall_kappa_binary_actioned": round(overall_bk, 3),
        "raw_percent_agreement": round(p_agree, 3),
        "by_stratum": by_stratum,
        "by_language": by_lang,
        "by_category": by_cat,
        "disagreement_pattern": dict(confusion.most_common()),
        "note": ("Second annotator is SIMULATED for reproducibility; replace with "
                 "real second labels to report human IAA. Interpretation "
                 "(Landis-Koch): 0.61-0.80 substantial, 0.81-1.0 almost perfect."),
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"IAA on n={report['n']} double-labeled subset")
    print(f"  Cohen's kappa (4-class severity): {report['overall_kappa_4class']}")
    print(f"  Cohen's kappa (binary actioned) : {report['overall_kappa_binary_actioned']}")
    print(f"  raw % agreement                 : {report['raw_percent_agreement']}")
    print("  by stratum:")
    for k, v in report["by_stratum"].items():
        print(f"    {k:12s} n={v['n']:2d}  kappa={v['kappa']:.3f}  agree={v['pct_agree']:.3f}")
    print("  by language:")
    for k, v in report["by_language"].items():
        print(f"    {k}: kappa={v['kappa']:.3f}  agree={v['pct_agree']:.3f}")
    print("  disagreement pattern (gold->second):")
    for k, v in report["disagreement_pattern"].items():
        print(f"    {k}: {v}")
    print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
