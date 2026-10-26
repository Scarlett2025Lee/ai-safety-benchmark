# Multilingual AI Safety Evaluation Benchmark

An English/Chinese content-safety benchmark with 600 base examples, expanding to 780 cases through neutral identity placeholders. It combines a policy taxonomy, annotation guidance, configurable prompts, evaluation metrics, and human-review routing experiments.

## Project scope

- Five categories: HAR, HAT, DAN, MIN, and MIS; see [taxonomy.md](taxonomy.md) for definitions.
- Four action tiers: S0 allow, S1 restrict, S2 remove, and S3 escalate.
- Safe, violating, boundary, and adversarial slices.
- Three prompt configurations: zero-shot policy, structured rubric, and few-shot boundary examples.
- Exact accuracy, within-one-tier accuracy, macro-F1, binary precision/recall/F1, false-negative rate, over-removal, and bootstrap confidence intervals for selected headline metrics.
- A deterministic mock runner and an optional Anthropic runner.
- Simulated inter-annotator agreement and human-review routing experiments.

## Run locally

Use Python 3.10 or newer. The mock workflow uses the Python standard library and does not require credentials.

```bash
cd harness
python run_benchmark.py --runner mock --config all --out results/
python compute_iaa.py
```

For a quick check, add `--limit 20`. For live model evaluation, install `anthropic`, set `ANTHROPIC_API_KEY` locally, and select a model available to your account:

```bash
python run_benchmark.py --runner anthropic --model YOUR_MODEL_ID --config structured_rubric --out results/
```

## Repository contents

| Location | Contents |
|---|---|
| `data/` | Original JSONL batches and calibration examples |
| `taxonomy.json` and `taxonomy.md` | Machine-readable rules and policy definitions |
| `annotation_guidelines.md` | Annotation instructions |
| `sampling_plan.md` | Sampling methodology |
| `escalation_strategy.md` | Review-routing strategy |
| `harness/safetybench/` | Dataset loading, prompts, model runners, metrics |
| `harness/` | Benchmark, agreement, escalation, and two-sample demo scripts |
| `harness/results/` (generated locally) | JSON reports produced by benchmark commands |

## How to interpret the results

**Mock-run reports are simulations, not measured model performance.** MockRunner deliberately uses gold labels to simulate predictions and exercise the reporting pipeline. The real runner does not receive that gold-label control channel.

`compute_iaa.py` simulates a second annotator. Its agreement statistics do not establish human annotation reliability. Human-review experiments are offline simulations, not production moderation outcomes.

The recovered archive did not include `run_flat.py` or `result_haiku_rubric.json`; this repository therefore makes no verified live-Haiku performance claim.

## Recovery and validation

Recovered from the previously uploaded project ZIP. The archive had flattened directory paths; Python package, dataset, and report folders were restored according to the imports and default paths. Bytecode caches and previously generated simulator reports were omitted; rerun the mock workflow to generate reports. Source modules and dataset records were preserved.

Validation: the dataset loader found 600 base / 780 expanded samples; a 20-case mock run completed for all three prompt configurations. No paid API evaluation was performed during recovery.

This is a portfolio evaluation tool, not a production safety enforcement service. Dataset labels and policy choices require review for any new deployment context.
