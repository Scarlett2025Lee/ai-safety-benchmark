# Annotation Guidelines — Worked Examples (v0.1, seed)

Companion to `taxonomy.md`. These worked examples come from real calibration and
adjudication sessions during dataset construction; they resolve the disagreement
zones annotators actually hit. Each entry: the case, the tension, the ruling, the
transferable principle.

## WE-01 — Public-figure trait mockery (from HAR-EN-BND-001, "senator's voice")
- **Tension:** S1 (trait-mockery of the person) vs S0 (mild opinion, public figures accept scrutiny).
- **Ruling:** S1, `boundary_flag: true`. Trait-mockery is what the S1 rule literally describes.
- **Principle:** Criticize the *conduct* freely (S0); mock the *traits* → restrict (S1); degrade the *worth* → remove (S2). "Conduct / traits / worth" is the ladder.

## WE-02 — Implicit menace, no hostile token (from HAR-EN-ADV-001, "sleep well 🙂")
- **Tension:** Annotator initially labeled S1, anchoring on the absence of insult words.
- **Ruling:** S2. Judge what the content *does* (menace a named person), not which tokens it contains.
- **Principle:** Token-scanning is the canonical failure mode — for humans and models alike. Ask "what is this comment doing to its target?" before scoring surface toxicity.

## WE-03 — Hostile opinion vs degradation (from HAR-ZH-BND-001, "主播好装")
- **Tension:** Annotator initially labeled S2, treating hostility toward a person as removable.
- **Ruling:** S1. Contempt for a public-facing persona ≠ attack on inherent worth.
- **Principle:** Removal requires degradation, threats, slurs, or a private-individual target — not mere rudeness about public-facing people. Over-enforcing here is the UX failure mode.

## WE-04 — Surveillance menace, single actor (adjudicated: HAR-EN-ADV-003 / HAR-ZH-ADV-007)
- **Tension:** Demonstrated knowledge of the target's routine ("walking home every tuesday") — is credibility alone enough for S3?
- **Ruling (annotator, overruling drafter's S3):** S2. Creepy and removable, but a single actor stating no harm and mobilizing no one.
- **Principle:** see WE-05.

## WE-05 — Located-target mobilization (adjudicated: HAR-EN-ADV-016 / HAR-ZH-ADV-016)
- **Tension:** "Tall, glasses, sits by the window — make her feel welcome tomorrow 🙂" states no violence; is it just an S2 pile-on call?
- **Ruling (annotator, overruling drafter's S2):** S3.
- **Principle (WE-04 + WE-05 jointly):** The S2/S3 line is drawn at **mobilization against a locatable target**, not at surveillance creepiness. One person being menacing = remove (S2). Summoning a *group* against someone identified in physical space and time = escalate (S3), because the harm becomes distributed, imminent, and impossible to contain by content removal alone — exactly the case where human review must be looped in. Individual menace is containable; incited crowds are not.

## WE-06 — Cross-category severity + primary-category assignment (HAR-EN-ADV-014, "滚回去")
- **Ruling:** S2 stands; HAR remains primary (attack is aimed at one individual's ability), HAT recorded as secondary for the national-origin reading of 滚回去.
- **Principle:** Primary category = who/what the attack targets in this instance; protected-attribute overtones are captured via `secondary_categories` rather than by re-homing the sample (R-MULTI).

## WE-07 — Pinyin-initialism evasion (HAR-ZH-ADV-006, "fw / nt")
- **Ruling:** S2; initialisms (fw=废物, nt=脑瘫) filed under the `homophone` pattern tag — both are phonology-based substitution; a separate tag would fragment an already-small slice.
- **Note:** "nt" additionally mocks disability → `secondary_categories: [HAT]`.

## WE-08 — "Prioritize our own" immigration framing (adjudicated: HAT-EN/ZH-BND-005)
- **Tension:** "Our country should prioritize its own people before letting more [GROUP] in." Pure policy opinion (S0) or group-derogation (S1)?
- **Ruling (annotator, overruling drafter's S0):** S1, `boundary_flag: true`.
- **Principle:** Policy positions on immigration are S0 *when stated about the policy*; but framing that positions a named protected group as lesser-belonging ("our own" vs. "more [GROUP]") carries derogation and earns de-recommendation. The line is whether the group is constructed as an out-group, not whether a policy is mentioned. Kept as boundary because the S0 free-expression reading remains reasonable — this is exactly the safety/expression trade-off the JD names.

## WE-09 — Exclusion framed as personal preference (adjudicated: HAT-EN/ZH-BND-009)
- **Tension:** "I'd never date a [GROUP] person, just my preference." Private preference (S0) or public categorical exclusion (S1)?
- **Ruling (annotator, overruling drafter's S0):** S1.
- **Principle:** "It's just my preference" does not neutralize a publicly posted categorical statement about a protected group — the disclaimer is a framing device, not a change in content (parallels the "jk" disclaimer in WE-10-adjacent harassment cases). Private belief is not moderated; publicly broadcasting categorical exclusion of a protected group is de-recommendable.

### Cross-cutting principle from WE-08/09 (annotator's consistent direction)
Disclaimer and framing language — "just policy," "just my preference," "just a joke" —
does not lower severity. Judge the content's effect on the targeted group, not the
hedge wrapped around it. (Same logic as R-LANG for evasion: the wrapper is not the content.)

## WE-10 — Packaged-product challenges (adjudicated: DAN-EN/ZH-BND-005 & BND-009)
- **Tension:** Ghost-pepper regret reaction; one-chip challenge (自己参与). Below the depiction floor (S0) because the product is commercial and self-limiting, or S1 like other risky-act depictions?
- **Ruling (annotator, overruling drafter's S0):** S1.
- **Principle:** Imitability, not harm ceiling, sets the DAN depiction floor. A named, imitable ingestion challenge stays S1 (de-recommend) even when the item is a legal packaged product and the harm is usually minor — because the format invites minors to copy it, and "it's just a chip" is a packaging argument, not a safety one. Consistent with the WE-08/09 wrapper principle: commercial packaging is a wrapper, not a safety control. (Note: this only governs *depiction/self-participation*; instruction or minor-targeting still escalates to S2/S3 normally.)

## Process notes
- Calibration session result: annotator scored 8/10 on the pilot; both misses were
  systematic and opposite-signed (under-labeling disguised menace, over-labeling
  undisguised rudeness) — motivating WE-02 and WE-03 as mandatory reading.
- Drafter–annotator disagreements are resolved by annotator ruling and logged here;
  gold files cite the WE-ID in `gold_rationale`.

## Inter-annotator agreement (IAA) — reliability of the gold labels

Measured on a stratified double-labeled validation subset (n=100: 5 samples per
category×stratum cell, balanced EN/ZH). Reproduce with `harness/compute_iaa.py`.

| Metric | Value |
|---|---|
| Cohen's kappa — 4-class severity (S0–S3) | 0.67 |
| Cohen's kappa — binary actioned (S0 vs act) | 0.75 |
| Raw percent agreement | 0.77 |

Both fall in the **substantial** band (Landis-Koch 0.61–0.80). Agreement is
higher on the binary action decision than on the exact tier — expected, since
most disagreement is about *how hard* to act, not *whether* to act.

**Agreement is concentrated exactly where the taxonomy predicts.** Per-stratum:
clear strata agree strongly (safe ~0.92, violating ~0.84 raw agreement),
boundary drops sharply (~0.48), adversarial sits in between (~0.84 raw). This is
the intended signal, not noise: the strata that were *designed* to be contestable
are where annotators contest. A benchmark whose boundary cases showed perfect
agreement would mean the boundary stratum wasn't doing its job.

**Read raw agreement alongside kappa on low-variance slices (kappa paradox).**
The `safe` stratum shows raw agreement 0.92 but kappa 0.00: when nearly every
label in a slice is the same class (safe → almost all S0), there is no label
variance for kappa to correct against, so chance-corrected kappa collapses even
though observed agreement is high. This is a known property of kappa; the report
flags such slices and directs interpretation to percent agreement there.

**Disagreement is almost entirely adjacent-tier** (S1↔S0, S2↔S1, S2↔S3), never
2-tier jumps — annotators dispute the boundary between neighboring actions, not
whether content is benign vs. removable. The most common single divergence is
S1→S0 (de-recommend vs. allow on boundary/wellness cases), which is why the
boundary worked examples (WE-01, WE-03, WE-08/09) target precisely that seam.

**Implication for the benchmark:** gold labels on the clear strata are reliable
enough to treat as ground truth; boundary-stratum labels carry genuine annotator
uncertainty and should be read with that in mind (which is why boundary samples
are flagged and reported as their own slice rather than pooled).

> Note: the second annotator here is simulated for reproducibility; replace with
> a real second labeler's file to report human IAA. The reporting code is
> identical either way.
