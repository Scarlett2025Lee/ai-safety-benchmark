"""Metrics: classification quality with bootstrap confidence intervals.

Design choices that matter for the write-up:

- We report BOTH the 4-class severity task (exact S0..S3 match, macro-F1 over
  four classes) AND a binary "actioned" view (S0 vs {S1,S2,S3}) because product
  decisions care about "did we act at all" and about "did we act correctly".
- False-negative rate (FNR) is computed on the binary actioned view: of all
  content that SHOULD have been actioned (gold != S0), how much did the model
  let through (predicted S0). This is the safety-critical miss rate.
- Confidence intervals are nonparametric bootstrap over samples, so tiny slices
  (e.g. zh-adversarial-homophone) honestly report wide intervals instead of
  pretending small-n point estimates are precise.
"""
from __future__ import annotations
import random
from collections import defaultdict
from dataclasses import dataclass

from .data import SEVERITIES, SEV_RANK


def _actioned(sev: str) -> bool:
    return sev != "S0"


@dataclass
class Metrics:
    n: int
    exact_accuracy: float
    macro_f1: float           # over 4 severity classes
    binary_precision: float   # actioned
    binary_recall: float      # actioned  (= 1 - FNR)
    binary_f1: float
    fnr: float                # false-negative rate on should-be-actioned
    over_removal: float       # gold S0 but predicted S2/S3 (false takedown)
    within_one_tier: float    # |pred - gold| <= 1 severity tier

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def compute(golds: list[str], preds: list[str]) -> Metrics:
    n = len(golds)
    if n == 0:
        return Metrics(0, *[0.0] * 8)

    exact = sum(g == p for g, p in zip(golds, preds)) / n
    within1 = sum(abs(SEV_RANK[g] - SEV_RANK[p]) <= 1
                  for g, p in zip(golds, preds)) / n

    # macro-F1 over the four severity classes
    f1s = []
    for cls in SEVERITIES:
        tp = sum(g == cls and p == cls for g, p in zip(golds, preds))
        fp = sum(g != cls and p == cls for g, p in zip(golds, preds))
        fn = sum(g == cls and p != cls for g, p in zip(golds, preds))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)
    macro_f1 = sum(f1s) / len(f1s)

    # binary actioned view
    btp = sum(_actioned(g) and _actioned(p) for g, p in zip(golds, preds))
    bfp = sum(not _actioned(g) and _actioned(p) for g, p in zip(golds, preds))
    bfn = sum(_actioned(g) and not _actioned(p) for g, p in zip(golds, preds))
    b_prec = btp / (btp + bfp) if (btp + bfp) else 0.0
    b_rec = btp / (btp + bfn) if (btp + bfn) else 0.0
    b_f1 = 2 * b_prec * b_rec / (b_prec + b_rec) if (b_prec + b_rec) else 0.0

    should_action = sum(_actioned(g) for g in golds)
    fnr = bfn / should_action if should_action else 0.0

    gold_safe = sum(not _actioned(g) for g in golds)
    over_removal = sum((not _actioned(g)) and SEV_RANK[p] >= SEV_RANK["S2"]
                       for g, p in zip(golds, preds)) / gold_safe if gold_safe else 0.0

    return Metrics(n, exact, macro_f1, b_prec, b_rec, b_f1, fnr,
                   over_removal, within1)


def bootstrap_ci(golds: list[str], preds: list[str], metric: str,
                 iters: int = 1000, seed: int = 0) -> tuple[float, float]:
    """95% bootstrap CI for a named Metrics field."""
    if not golds:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(golds)
    vals = []
    idx = list(range(n))
    for _ in range(iters):
        sample = [rng.choice(idx) for _ in range(n)]
        g = [golds[i] for i in sample]
        p = [preds[i] for i in sample]
        vals.append(getattr(compute(g, p), metric))
    vals.sort()
    lo = vals[int(0.025 * iters)]
    hi = vals[int(0.975 * iters)]
    return (lo, hi)


def slice_metrics(rows: list[dict], by: str) -> dict[str, Metrics]:
    """rows: list of {gold, pred, <slice keys...>}. Returns metrics per group."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = r.get(by)
        if key is None:
            continue
        groups[str(key)].append(r)
    out = {}
    for key, grp in sorted(groups.items()):
        out[key] = compute([r["gold"] for r in grp], [r["pred"] for r in grp])
    return out
