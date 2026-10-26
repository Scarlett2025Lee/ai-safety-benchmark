# Escalation Strategy — Human-in-the-Loop Routing

Reproduce: `python harness/escalation.py` → `harness/results/escalation.json`.

## Why route at all
The benchmark shows the model is not safe to run fully autonomously: overall FNR
~19% (≈1 in 5 should-be-actioned items let through), concentrated in the
adversarial and boundary strata, and least reliable exactly where stakes are
highest (minor-safety, credible threats). The response is not "trust the model"
or "review everything" — it's a routing policy that sends the right subset to
human review, chosen against an explicit recall-vs-workload trade-off.

## Triggers (route to human when any fires)
1. **High-stakes floor** — minor-safety category and any S3 prediction are always
   reviewed. Justified by *asymmetric cost*, not recall efficiency: an autonomous
   miss here is categorically unacceptable regardless of model confidence.
2. **Evasion-likelihood** — items with disguise signals (homophone, leetspeak,
   code-switch, implicit) are routed. This targets the model's single worst
   slice; in the harness it is proxied by the adversarial stratum.
3. **Boundary band** — predictions at/near the S1 allow/act line, where error
   concentrates and where inter-annotator agreement is itself lowest (κ analysis).
4. **Ensemble disagreement** — when two configs (or models) disagree on the
   action decision. *Reported but found weak here* (see below).

## Measured trade-off (mock simulation, n=780)

| Policy | Review % | Safety recall | FNR | Enf. precision |
|---|---|---|---|---|
| model only | 0% | 0.806 | 0.194 | 0.905 |
| + high-stakes floor | 17.4% | 0.817 | 0.183 | 0.944 |
| + evasion routing | 33.6% | 0.881 | 0.119 | 0.948 |
| + boundary band | 53.1% | 0.963 | 0.037 | 0.963 |
| + config disagreement | 53.1% | 0.963 | 0.037 | 0.963 |

**Marginal review efficiency (recall gained per +1% of content reviewed):**
- high-stakes floor: +0.06 pts/1% — *not a recall play; a cost-asymmetry play*
- evasion routing: **+0.40 pts/1%** — best recall-per-review
- boundary band: +0.42 pts/1% — sustains the gain
- config disagreement: +0.00 — adds nothing

## Recommended operating point
**High-stakes floor + evasion routing** (~34% review, recall 0.88, FNR 0.12) as
the default, extending into the boundary band when review budget allows (→ recall
0.96). The floor is mandatory on cost grounds; evasion routing is the efficient
recall lever; the boundary band is the next increment; config disagreement is
dropped.

## Two honest findings worth stating explicitly
- **Config disagreement barely helps.** Two prompt configurations of the *same*
  weak model largely share blind spots, so ensemble instability rarely flags the
  model's true misses. Real lift would require a genuinely different second model,
  not a second prompt — a concrete, testable next step, not a solved item.
- **Human review is idealized as returning the gold label.** That bounds the
  achievable recall; real reviewers have their own error and latency, so
  deployed recall would be somewhat lower. The curve is the *ceiling* of what
  routing can buy, which is the right way to frame a design trade-off.

## What a PM does with this
Pick the operating point from the reviewer budget: given N reviewer-hours and an
average handle time, the review-% column converts directly to required staffing,
and the recall column says what safety level that budget buys. The decision
becomes "we can staff X% review, which yields Y recall and Z FNR" — defensible,
quantified, and revisitable as the model improves and the curve shifts left.
