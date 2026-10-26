# Dataset Sampling Plan (v1.0)

600 synthetic short-form content samples (comment/caption register), stratified by
language × policy category × stratum. Gold labels assigned per `taxonomy.md` rules.

## Top-level split

- **Language:** 300 EN / 300 ZH (equal, so per-language metrics have equal power)
- **Category:** 60 samples per category per language (equal category totals keep
  per-category metrics comparable)
- **Stratum mix varies by category** — adversarial samples are weighted toward
  categories with realistic evasion pressure (harassment, hate speech), with a floor
  of 8 per category per language so no category is a robustness blind spot.

## Per-language allocation (×2 languages)

| Category | Safe | Violating | Boundary | Adversarial | Total |
|----------|------|-----------|----------|-------------|-------|
| HAR harassment/bullying   | 16 | 16 | 12 | **16** | 60 |
| HAT hate speech           | 16 | 16 | 12 | **16** | 60 |
| MIS health misinfo        | 17 | 17 | 14 | **12** | 60 |
| DAN dangerous acts        | 19 | 19 | 14 | **8**  | 60 |
| MIN minor safety          | 19 | 19 | 14 | **8**  | 60 |
| **Total per language**    | 87 | 87 | 66 | **60** | 300 |

Rationale for weighting: evasion effort concentrates where posters are motivated to
repeatedly bypass filters (coordinated harassment, coded hate speech). Dangerous
challenges are typically overt (virality requires visibility). Floor of 8 preserves
minimal robustness signal everywhere, incl. minor safety.

## Stratum definitions

- **Safe (S0 gold label):** Compliant content. Must include **hard negatives** —
  content superficially resembling violations: condemnation quoting abuse, news
  reporting on a dangerous trend, reclaimed in-group language, debunking posts,
  self-deprecating jokes, banter. ≥50% of safe samples per category are hard
  negatives. (These measure over-enforcement / false positives, which the JD's
  "trade-offs between safety, fairness, user experience" language is about.)
- **Violating (S2/S3):** Unambiguous violations stated plainly. Include a small
  number of S3 escalation cases (~2 per category per language).
- **Boundary (S1, or contested S0/S1):** Cases where two tiers are defensible and
  the taxonomy's R-DOUBT rule applies: public-figure mockery, professional stunts
  without safety framing, unproven-but-not-dangerous wellness claims.
- **Adversarial (gold label = the underlying violation):** Violating content with a
  detection-evasion pattern applied. Per taxonomy rule R-LANG, evasion does not
  reduce severity — gold label matches the undisguised equivalent.

## Adversarial pattern inventory (tagged per sample)

| Pattern tag | Description | Example mechanism |
|-------------|-------------|-------------------|
| `euphemism` | Indirect phrasing of the violating act | "unalive," "accountant" slang |
| `homophone` | Sound-alike character/word substitution | ZH 谐音字; EN deliberate misspelling |
| `leetspeak` | Character-level obfuscation | h8, @ substitution, zero-width splits |
| `code_switch`| Violation split across EN/ZH in one sample | insult in ZH inside an EN sentence |
| `implicit`  | Meaning requires inference, no banned token present | "people like you know what you deserve" |
| `irony_mask`| Violation wrapped in mock-joking frame | "just kidding unless…" pattern |
| `fragmented`| Violation completed across caption + implied context | requires composing parts |

Each adversarial sample carries exactly one primary pattern tag → enables the Phase 6
slice analysis "by adversarial pattern."

## Sample record schema (JSONL)

```json
{
  "id": "HAR-ZH-ADV-007",
  "lang": "zh",
  "category": "HAR",
  "stratum": "adversarial",
  "adversarial_pattern": "homophone",
  "text": "...",
  "gold_severity": "S2",
  "gold_rationale": "one-line rule citation, e.g. HAR rule 2 + R-LANG",
  "secondary_categories": [],
  "boundary_flag": false
}
```

## Known limitations (state these proactively)

1. **Synthetic data**: no real user-data distribution; register realism depends on
   authoring quality. Mitigation: author in comment/caption register, vary length
   and tone; treat absolute scores as indicative, deltas between models/slices as
   the primary signal.
2. **Small slices**: adversarial-pattern × language cells are small (n≈4–8);
   report bootstrap 95% CIs and avoid ranking claims within overlapping intervals.
3. **Single-annotator gold labels** except the double-labeled validation subset
   (Phase 3) used to estimate label reliability.
