# safetybench — evaluation harness

Reproducible harness for the Multilingual (EN/ZH) AI Safety Evaluation Benchmark.
Loads the 600-sample gold set, instantiates placeholders, runs a model under one
or more prompt configurations, and reports precision / recall / macro-F1 /
false-negative rate with bootstrap 95% CIs, sliced by language, category,
severity stratum, and adversarial pattern.

## Layout
```
harness/
├── run_benchmark.py          # CLI entry point
├── safetybench/
│   ├── data.py               # load samples; placeholder instantiation (+ fairness probe)
│   ├── prompts.py            # 3 prompt configs (zero-shot / rubric / few-shot)
│   ├── models.py             # MockRunner (no key) + AnthropicRunner (real)
│   └── metrics.py            # metrics + nonparametric bootstrap CIs + slices
└── results/                  # JSON reports written by --out
```

## Quick start (no API key)
```bash
cd harness
python run_benchmark.py --runner mock --config all --out results/
```
The mock is a **simulator**, not a model: it derives predictions from the gold
label with calibrated, stratum-/language-dependent error so the pipeline is
demoable end-to-end. Its numbers illustrate the report format only — never cite
them as real model performance.

## Real evaluation
```bash
pip install anthropic
export ANTHROPIC_API_KEY=...
python run_benchmark.py --runner anthropic --model claude-sonnet-4-5 --config structured_rubric --out results/
```
Add a provider by implementing a `.classify(messages) -> {"severity","category","rationale"}`
runner in `models.py`.

## Prompt configurations
- `zero_shot_policy` — severity definitions only.
- `structured_rubric` — full machine-readable rules + the evasion/context guidance.
- `few_shot_boundary` — rubric plus four worked boundary examples.

Comparing these isolates how much safety performance comes from the model vs.
from how the policy is presented.

## Metrics
- **exact severity accuracy** and **within-one-tier** (4-class S0–S3).
- **macro-F1** over the four severity classes.
- **binary actioned view** (S0 vs S1/S2/S3): precision, recall, F1.
- **FNR** — of content that should be actioned, the fraction let through (the
  safety-critical miss rate).
- **over-removal** — of gold-S0 content, the fraction taken down (S2/S3): the
  UX-critical false-positive rate.
- All headline metrics carry nonparametric bootstrap 95% CIs, so small slices
  report honest uncertainty instead of overconfident point estimates.

## Placeholder instantiation & fairness probe
HAT samples ship with `[GROUP]`/`[群体]`/`[SLUR]`/`[蔑称]` placeholders (no real
slurs or named protected groups in the repo). At run time each template is
instantiated against a configurable identity list; the same template run across
identities doubles as a fairness check — a well-behaved model should score
identical hateful templates identically regardless of the group in the slot.
```
600 base samples -> 780 after placeholder expansion (default 3 identities)
```
