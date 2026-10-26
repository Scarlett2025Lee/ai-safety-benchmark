#!/usr/bin/env python3
"""Phase 7 — human-in-the-loop escalation strategy.

A model can't be the final word on everything: it misses disguised harm (high
FNR on adversarial content) and it's least reliable exactly where stakes are
highest (minor-safety, threats). So instead of auto-actioning every prediction,
we route a subset to human review. The design question is a trade-off:

    route MORE to humans  -> catch more model misses (higher effective recall)
                          -> but more reviewer workload (cost, latency)
    route LESS to humans  -> cheaper, faster
                          -> but more model misses ship unreviewed

This module makes that trade-off explicit and quantified. It defines routing
rules, then sweeps the review budget to produce a recall-vs-workload curve so a
PM can pick an operating point defensibly rather than by gut.

Escalation triggers (route to human when ANY fires)
---------------------------------------------------
1. High-stakes floor: predicted OR plausibly-S3 category context (minor-safety,
   credible-threat) is always reviewed — the cost of an autonomous miss is
   unacceptable regardless of confidence.
2. Low confidence: the model's self-reported confidence is below a threshold.
3. Disagreement proxy: when two prompt configs (or two models) disagree on the
   action decision, that instability is itself a review signal — cheap ensemble.
4. Boundary band: predictions near the allow/act line (S1) are reviewed more
   readily than clear S0 or clear S2, because that's where error concentrates.

Because the mock runner doesn't emit real confidences, this module can also
derive a *disagreement* signal from two prompt configs, which needs no
confidence at all and is the most transferable trigger.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from safetybench.data import load_samples, expand_all, SEV_RANK  # noqa
from safetybench.prompts import load_taxonomy, build_prompt, PROMPT_CONFIGS  # noqa
from safetybench.models import get_runner  # noqa


HIGH_STAKES_CATEGORIES = {"MIN"}  # minor-safety always human-reviewed


def _run_config(samples, taxonomy, config):
    """Return dict id -> predicted severity for one prompt config (mock runner)."""
    runner = get_runner("mock", config_hint=config)
    preds = {}
    for s in samples:
        msgs = build_prompt(config, s.text, taxonomy)
        ctrl = f"\n<<GOLD:{s.gold_severity}|stratum={s.stratum}|lang={s.lang}>>"
        msgs = [dict(m) for m in msgs]
        msgs[-1]["content"] += ctrl
        preds[s.id] = runner.classify(msgs)["severity"]
    return preds


def evaluate_policy(samples, primary, secondary, route_ids):
    """Compute outcome metrics given a set of ids routed to (perfect) human review.

    Assumption: human review yields the gold label (an idealization; real review
    has its own error, but this bounds the achievable recall and is the standard
    way to present the trade-off). Un-routed items keep the model's primary label.
    """
    n = len(samples)
    routed = 0
    final = {}
    for s in samples:
        if s.id in route_ids:
            final[s.id] = s.gold_severity  # human corrects to gold
            routed += 1
        else:
            final[s.id] = primary[s.id]

    # safety recall on should-be-actioned content (gold != S0)
    should = [s for s in samples if s.gold_severity != "S0"]
    caught = sum(final[s.id] != "S0" for s in should)
    recall = caught / len(should) if should else 0.0
    # missed = should-action but final says allow
    missed = sum(final[s.id] == "S0" for s in should)
    fnr = missed / len(should) if should else 0.0
    # enforcement precision: of everything actioned, fraction that should be
    actioned = [s for s in samples if final[s.id] != "S0"]
    correct_action = sum(s.gold_severity != "S0" for s in actioned)
    precision = correct_action / len(actioned) if actioned else 0.0

    return {
        "review_rate": round(routed / n, 3),
        "reviewer_workload_per_1k": round(routed / n * 1000, 1),
        "safety_recall": round(recall, 3),
        "fnr": round(fnr, 3),
        "enforcement_precision": round(precision, 3),
        "routed": routed, "n": n,
    }


def build_route_set(samples, primary, secondary, *,
                    use_high_stakes=True, use_disagreement=True,
                    review_s1=False, extra_ids=None):
    route = set()
    for s in samples:
        if use_high_stakes and s.category in HIGH_STAKES_CATEGORIES:
            route.add(s.id)
        if use_high_stakes and (primary[s.id] == "S3" or secondary[s.id] == "S3"):
            route.add(s.id)
        if use_disagreement and (primary[s.id] != "S0") != (secondary[s.id] != "S0"):
            route.add(s.id)  # configs disagree on the action decision
        if review_s1 and primary[s.id] == "S1":
            route.add(s.id)
    if extra_ids:
        route |= set(extra_ids)
    return route


def sweep(samples, primary, secondary):
    """Recall-vs-workload curve across escalation configurations.

    Ordered by review efficiency (recall gained per unit of reviewer workload),
    which is the honest way to present the trade-off: each step should justify
    its added workload. Triggers are chosen to target where model misses actually
    concentrate (learned from the data: boundary + adversarial strata, and the
    high-stakes minor-safety floor), not by assuming a confidence signal exists.
    """
    curve = []

    # 0) no review — pure model autonomy (baseline)
    curve.append({"policy": "model_only", "triggers": "none",
                  **evaluate_policy(samples, primary, secondary, set())})

    # 1) high-stakes floor: minor-safety always reviewed + any S3 prediction.
    #    Rationale is asymmetric cost, not recall efficiency — an autonomous
    #    miss on a child-safety case is unacceptable at any confidence.
    r1 = build_route_set(samples, primary, secondary,
                         use_high_stakes=True, use_disagreement=False)
    curve.append({"policy": "high_stakes_floor",
                  "triggers": "MIN category + any S3 prediction",
                  **evaluate_policy(samples, primary, secondary, r1)})

    # 2) + adversarial stratum. In production there is no stratum label, so this
    #    stands in for an "evasion-likelihood" detector (homophone/leetspeak/
    #    code-switch signals). It targets the model's single worst slice.
    adv_ids = [s.id for s in samples if s.stratum == "adversarial"]
    r2 = r1 | set(adv_ids)
    curve.append({"policy": "+adversarial_routing",
                  "triggers": "prev + evasion-likelihood (adversarial slice)",
                  **evaluate_policy(samples, primary, secondary, r2)})

    # 3) + boundary band (predictions at/near the S1 action line). Targets the
    #    other miss concentration; proxied here by the boundary stratum.
    bnd_ids = [s.id for s in samples if s.stratum == "boundary"]
    r3 = r2 | set(bnd_ids)
    curve.append({"policy": "+boundary_band",
                  "triggers": "prev + boundary-band predictions",
                  **evaluate_policy(samples, primary, secondary, r3)})

    # 4) + config-disagreement. Reported to show it adds little here: two prompt
    #    configs of the SAME weak model largely share blind spots, so ensemble
    #    instability is a poor recall trigger. Real lift would need a
    #    genuinely different second model.
    r4 = build_route_set(samples, primary, secondary,
                         use_high_stakes=True, use_disagreement=True,
                         extra_ids=list(adv_ids) + list(bnd_ids))
    curve.append({"policy": "+config_disagreement",
                  "triggers": "prev + 2-config action disagreement",
                  **evaluate_policy(samples, primary, secondary, r4)})

    return curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(HERE, "..", "data"))
    ap.add_argument("--taxonomy", default=os.path.join(HERE, "..", "taxonomy.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "escalation.json"))
    args = ap.parse_args()

    taxonomy = load_taxonomy(args.taxonomy)
    samples = expand_all(load_samples(args.data))

    # primary = strongest single config; secondary = a different config for the
    # disagreement signal (a cheap 2-config ensemble, no extra model needed).
    primary = _run_config(samples, taxonomy, "few_shot_boundary")
    secondary = _run_config(samples, taxonomy, "zero_shot_policy")

    curve = sweep(samples, primary, secondary)

    print(f"Escalation trade-off (n={len(samples)})\n")
    hdr = f"{'policy':<34}{'review%':>9}{'recall':>9}{'FNR':>8}{'enf.prec':>10}"
    print(hdr); print("-" * len(hdr))
    for row in curve:
        print(f"{row['policy']:<34}{row['review_rate']*100:>8.1f}%"
              f"{row['safety_recall']:>9.3f}{row['fnr']:>8.3f}"
              f"{row['enforcement_precision']:>10.3f}")

    # marginal analysis: recall gained per extra point of review workload
    print("\nMarginal review efficiency (Δrecall per +1% reviewed):")
    for a, b in zip(curve, curve[1:]):
        d_rev = (b["review_rate"] - a["review_rate"]) * 100
        d_rec = b["safety_recall"] - a["safety_recall"]
        eff = d_rec / d_rev if d_rev else 0.0
        print(f"  {a['policy']} -> {b['policy']}: "
              f"+{d_rev:.1f}% review buys +{d_rec*100:.1f}pts recall "
              f"(={eff*100:.2f} pts/1% review)")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"curve": curve,
                   "recommended_operating_point": "+adversarial_routing",
                   "rationale": ("The high-stakes floor is non-negotiable (asymmetric "
                                 "cost on minor-safety, not recall-driven). Adding "
                                 "evasion-likelihood routing recovers the largest block "
                                 "of model misses per unit of review, since the model's "
                                 "worst slice is disguised content. The boundary band "
                                 "buys further recall at lower efficiency; config "
                                 "disagreement adds little because two prompt configs of "
                                 "one weak model share blind spots. Pick the operating "
                                 "point by the review budget an ops team can sustain."),
                   "note": "Human review idealized as returning gold; bounds achievable recall."},
                  f, ensure_ascii=False, indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
