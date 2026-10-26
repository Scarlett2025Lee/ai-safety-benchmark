"""Dataset loading and placeholder instantiation.

The HAT (hate-speech) samples use HateCheck-style placeholders so the public
repo never ships spelled-out slurs or names real protected groups. At eval
time we instantiate each placeholder from a configurable identity list. The
SAME template can be run against multiple identities, which doubles as a
fairness probe: a well-behaved model should score "GROUP are vermin"
identically regardless of which group fills the slot.
"""
from __future__ import annotations
import json
import glob
import os
from dataclasses import dataclass, field
from typing import Iterable

SEVERITIES = ["S0", "S1", "S2", "S3"]
SEV_RANK = {s: i for i, s in enumerate(SEVERITIES)}
CATEGORIES = ["HAR", "HAT", "DAN", "MIN", "MIS"]
STRATA = ["safe", "violating", "boundary", "adversarial"]

# Neutral placeholder fillers. Real deployments swap in the platform's actual
# protected-attribute list; these keep the repo publishable while exercising
# the same code path. [SLUR]/[蔑称] are filled with a neutral stand-in token so
# no real slur is ever emitted by the harness.
DEFAULT_IDENTITIES = {
    "en": ["group A", "group B", "group C"],
    "zh": ["某群体甲", "某群体乙", "某群体丙"],
}
NEUTRAL_SLUR = {"en": "[derogatory-term]", "zh": "[蔑称词]"}


@dataclass
class Sample:
    id: str
    lang: str
    category: str
    stratum: str
    text: str
    gold_severity: str
    adversarial_pattern: str | None = None
    gold_rationale: str = ""
    secondary_categories: list = field(default_factory=list)
    boundary_flag: bool = False
    # populated when a placeholder template is instantiated
    identity: str | None = None

    @property
    def has_placeholder(self) -> bool:
        return any(tok in self.text for tok in
                   ("[GROUP]", "[群体]", "[SLUR]", "[蔑称]", "[GROUP-MISSPELLED]"))


def load_samples(data_dir: str) -> list[Sample]:
    """Load every .jsonl in data_dir into Sample objects (deduplicated by id)."""
    seen: set[str] = set()
    out: list[Sample] = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                if o["id"] in seen:
                    continue
                seen.add(o["id"])
                out.append(Sample(
                    id=o["id"], lang=o["lang"], category=o["category"],
                    stratum=o["stratum"], text=o["text"],
                    gold_severity=o["gold_severity"],
                    adversarial_pattern=o.get("adversarial_pattern"),
                    gold_rationale=o.get("gold_rationale", ""),
                    secondary_categories=o.get("secondary_categories", []),
                    boundary_flag=o.get("boundary_flag", False),
                ))
    return out


def instantiate(sample: Sample, identities: dict | None = None) -> list[Sample]:
    """Expand a placeholder template into one concrete Sample per identity.

    Non-placeholder samples are returned unchanged (as a 1-element list).
    Placeholder samples yield one instance per configured identity, so the
    harness can measure cross-identity consistency.
    """
    identities = identities or DEFAULT_IDENTITIES
    if not sample.has_placeholder:
        return [sample]
    fillers = identities.get(sample.lang, identities["en"])
    slur = NEUTRAL_SLUR.get(sample.lang, NEUTRAL_SLUR["en"])
    out = []
    for ident in fillers:
        text = (sample.text
                .replace("[GROUP-MISSPELLED]", ident)
                .replace("[GROUP]", ident).replace("[群体]", ident)
                .replace("[SLUR]", slur).replace("[蔑称]", slur))
        out.append(Sample(
            id=f"{sample.id}::{ident}", lang=sample.lang,
            category=sample.category, stratum=sample.stratum, text=text,
            gold_severity=sample.gold_severity,
            adversarial_pattern=sample.adversarial_pattern,
            gold_rationale=sample.gold_rationale,
            secondary_categories=list(sample.secondary_categories),
            boundary_flag=sample.boundary_flag, identity=ident,
        ))
    return out


def expand_all(samples: Iterable[Sample], identities: dict | None = None) -> list[Sample]:
    out: list[Sample] = []
    for s in samples:
        out.extend(instantiate(s, identities))
    return out
