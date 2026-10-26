"""Model runners.

Two runners share one interface, `.classify(messages) -> dict`:

- MockRunner: deterministic, no API key, no network. It simulates a plausible
  moderation model *including realistic failure modes* — it under-detects
  adversarial/implicit content and is weaker in Chinese — so the whole harness
  (metrics, slices, CIs, escalation) can be exercised and demoed end to end
  without credentials. It is NOT a real model; its only purpose is to make the
  pipeline runnable and testable.
- AnthropicRunner: calls a real model. Requires ANTHROPIC_API_KEY and the
  `anthropic` package. Swap in any provider by implementing `.classify`.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from typing import Protocol

from .data import SEVERITIES


class Runner(Protocol):
    name: str
    def classify(self, messages: list[dict]) -> dict: ...


def _parse_json_response(raw: str) -> dict:
    """Extract the {severity, category, rationale} object from a model reply."""
    raw = raw.strip()
    raw = re.sub(r"^```(json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        obj = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        obj = json.loads(m.group(0)) if m else {}
    sev = str(obj.get("severity", "")).upper()
    if sev not in SEVERITIES:
        sev = "S0"  # unparseable defaults to allow; counted as a miss vs gold
    return {"severity": sev,
            "category": obj.get("category", "none"),
            "rationale": obj.get("rationale", "")}


# --------------------------------------------------------------------------- #
# Mock runner
# --------------------------------------------------------------------------- #
class MockRunner:
    """Deterministic SIMULATOR of a plausible moderation model.

    This is NOT a real classifier and does no language understanding. To make
    the pipeline demoable without an API key, it derives a prediction from the
    gold label and then applies calibrated, stratum-/language-dependent error
    so the *shape* of the output resembles a real EN-centric model:
      - competent on plain violating and safe content,
      - degraded on boundary cases,
      - much weaker on adversarial (disguised) content,
      - weaker in Chinese than English,
      - reluctant to self-escalate to S3,
      - a little over-removal on scary-looking hard negatives.
    Prompt config modulates the adversarial recovery (few-shot helps most).
    Replace with AnthropicRunner for real numbers. The gold label is read from
    a control channel injected by the harness, never from real model reasoning.
    """
    name = "mock-v1"

    def __init__(self, config_hint: str = "", seed: int = 0):
        self.config_hint = config_hint
        self.seed = seed

    def _u(self, key: str, salt: str = "") -> float:
        h = hashlib.md5(f"{self.seed}:{salt}:{key}".encode("utf-8")).hexdigest()
        return (int(h[:8], 16) % 10_000) / 10_000.0

    def classify(self, messages: list[dict]) -> dict:
        # The harness passes a hidden control line the mock reads; a real runner
        # ignores it. Format: "<<GOLD:S2|stratum=adversarial|lang=zh>>"
        raw = messages[-1]["content"]
        ctrl = {}
        if "<<GOLD:" in raw:
            seg = raw.split("<<GOLD:", 1)[1].split(">>", 1)[0]
            parts = seg.split("|")
            ctrl["gold"] = parts[0]
            for p in parts[1:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    ctrl[k] = v
        gold = ctrl.get("gold", "S0")
        stratum = ctrl.get("stratum", "violating")
        lang = ctrl.get("lang", "en")
        u = self._u(raw)

        pred = gold  # start from truth, then corrupt realistically

        # base per-stratum accuracy (probability of keeping the correct tier)
        keep = {"safe": 0.93, "violating": 0.86,
                "boundary": 0.55, "adversarial": 0.42}[stratum]
        # Chinese penalty
        if lang == "zh":
            keep -= 0.10
        # adversarial recovery by prompt config
        if stratum == "adversarial":
            if self.config_hint == "structured_rubric":
                keep += 0.08
            elif self.config_hint == "few_shot_boundary":
                keep += 0.16

        if u < keep:
            pred = gold
        else:
            # error direction: for should-be-actioned content the dominant
            # real-world error is UNDER-enforcement (drop toward S0)
            if gold in ("S2", "S3"):
                v = self._u(raw, "dir")
                pred = "S1" if v < 0.45 else "S0"
            elif gold == "S1":
                v = self._u(raw, "dir")
                pred = "S0" if v < 0.6 else "S2"
            else:  # gold S0 -> occasional over-removal
                v = self._u(raw, "dir")
                pred = "S1" if v < 0.7 else "S2"

        # models rarely self-escalate to S3
        if pred == "S3" and self._u(raw, "esc") < 0.6:
            pred = "S2"

        return {"severity": pred, "category": "none", "rationale": "mock simulation"}


# --------------------------------------------------------------------------- #
# Real Anthropic runner
# --------------------------------------------------------------------------- #
class AnthropicRunner:
    """Calls a real Anthropic model. Requires ANTHROPIC_API_KEY."""
    def __init__(self, model: str = "claude-sonnet-4-5", max_tokens: int = 200):
        try:
            import anthropic  # noqa
        except ImportError as e:
            raise RuntimeError(
                "pip install anthropic to use AnthropicRunner") from e
        self._anthropic = __import__("anthropic")
        self.client = self._anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model
        self.name = model
        self.max_tokens = max_tokens

    def classify(self, messages: list[dict]) -> dict:
        system = "".join(m["content"] for m in messages if m["role"] == "system")
        user = [m for m in messages if m["role"] == "user"]
        resp = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            messages=[{"role": "user", "content": user[-1]["content"]}],
        )
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _parse_json_response(raw)


def get_runner(kind: str, config_hint: str = "", model: str = "claude-sonnet-4-5") -> Runner:
    if kind == "mock":
        return MockRunner(config_hint=config_hint)
    if kind == "anthropic":
        return AnthropicRunner(model=model)
    raise ValueError(f"unknown runner kind: {kind}")
