"""Per-stage LLM cost accounting for the PDF extraction pipeline.

Every LLM call records its token usage (input / cached input / output /
reasoning) tagged by pipeline stage. At the end of a run the tracker writes a
clear per-stage + total breakdown next to the other debug artifacts:

    storage/extraction_debug/<session_id>/llm_cost.json   (machine-readable)
    storage/extraction_debug/<session_id>/llm_cost.txt    (human-readable)

Costs are computed from MODEL_PRICING below. Prices are USD per 1,000,000
tokens and MUST be kept in sync with OpenAI's official pricing page — update
them here when a model's price changes or a new model is adopted. If a model is
not in the table, tokens are still recorded and cost is reported as null
("pricing_configured": false) rather than guessed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Pricing table (USD per 1,000,000 tokens) ─────────────────────────────────
#
# Each entry: input (uncached), cached_input, output.
# `verified` marks whether the numbers were taken from OpenAI's pricing page
# (True) or derived/estimated (False) — both compute a cost, but unverified
# entries are flagged in the report so they are not mistaken for ground truth.
@dataclass(frozen=True)
class Pricing:
    input: float
    cached_input: float
    output: float
    verified: bool = True


MODEL_PRICING: Dict[str, Pricing] = {
    # Primary model for this pipeline (sourced from public pricing coverage).
    "gpt-6.1-terra": Pricing(input=1.00, cached_input=0.05, output=5.00, verified=True),
    # Derived: reported as ~2x Terra. Update with official numbers when adopted.
    "gpt-6.1-sol": Pricing(input=2.00, cached_input=0.10, output=10.00, verified=False),
    # gpt-5.6 family (public coverage; cached rate estimated at 10% of input).
    "gpt-5.6-sol": Pricing(input=5.00, cached_input=0.50, output=30.00, verified=False),
    "gpt-5.6-terra": Pricing(input=2.50, cached_input=0.25, output=15.00, verified=False),
    "gpt-5.6-luna": Pricing(input=1.00, cached_input=0.10, output=6.00, verified=False),
    # Fallback / legacy models.
    "gpt-4.1-mini": Pricing(input=0.40, cached_input=0.10, output=1.60, verified=False),
    "gpt-4.1": Pricing(input=2.00, cached_input=0.50, output=8.00, verified=False),
    "gpt-4o-mini": Pricing(input=0.15, cached_input=0.075, output=0.60, verified=False),
    "gpt-4o": Pricing(input=2.50, cached_input=1.25, output=10.00, verified=False),
}


def _lookup_pricing(model: str) -> Optional[Pricing]:
    """Exact match first, then the longest known prefix (handles dated snapshot
    ids like `gpt-6.1-terra-2026-10-27`)."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    candidates = [k for k in MODEL_PRICING if model.startswith(k)]
    if not candidates:
        return None
    return MODEL_PRICING[max(candidates, key=len)]


# ── Per-call record ──────────────────────────────────────────────────────────

@dataclass
class CallRecord:
    stage: str
    model: str
    reasoning_effort: Optional[str]
    label: Optional[str]
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cost_usd: Optional[float]
    pricing_configured: bool
    pricing_verified: bool

    @property
    def uncached_input_tokens(self) -> int:
        return max(self.input_tokens - self.cached_input_tokens, 0)


# ── Tracker ──────────────────────────────────────────────────────────────────

class CostTracker:
    """Accumulates per-call usage and writes a per-stage + total cost report."""

    def __init__(self, session_id: str, model: str):
        self.session_id = session_id
        self.model = model
        self.calls: List[CallRecord] = []

    def record(
        self,
        *,
        stage: str,
        model: str,
        reasoning_effort: Optional[str],
        usage_metadata: Optional[Dict[str, Any]],
        label: Optional[str] = None,
    ) -> None:
        """Record one LLM call from a LangChain usage_metadata dict.

        Best-effort: never raises. A call with no usage metadata is recorded with
        zero tokens so the call still appears in the per-stage count.
        """
        usage = usage_metadata or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cached = int((usage.get("input_token_details") or {}).get("cache_read") or 0)
        reasoning = int((usage.get("output_token_details") or {}).get("reasoning") or 0)

        pricing = _lookup_pricing(model)
        if pricing is None:
            cost: Optional[float] = None
        else:
            uncached = max(input_tokens - cached, 0)
            cost = round(
                uncached / 1_000_000 * pricing.input
                + cached / 1_000_000 * pricing.cached_input
                + output_tokens / 1_000_000 * pricing.output,
                6,
            )

        self.calls.append(
            CallRecord(
                stage=stage,
                model=model,
                reasoning_effort=reasoning_effort,
                label=label,
                input_tokens=input_tokens,
                cached_input_tokens=cached,
                output_tokens=output_tokens,
                reasoning_tokens=reasoning,
                cost_usd=cost,
                pricing_configured=pricing is not None,
                pricing_verified=bool(pricing and pricing.verified),
            )
        )

    # ── Aggregation ──────────────────────────────────────────────────────────

    def _aggregate(self) -> Dict[str, Dict[str, Any]]:
        stages: Dict[str, Dict[str, Any]] = {}
        for c in self.calls:
            s = stages.setdefault(
                c.stage,
                {
                    "calls": 0,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "cost_usd": 0.0,
                    "cost_complete": True,
                },
            )
            s["calls"] += 1
            s["input_tokens"] += c.input_tokens
            s["cached_input_tokens"] += c.cached_input_tokens
            s["output_tokens"] += c.output_tokens
            s["reasoning_tokens"] += c.reasoning_tokens
            if c.cost_usd is None:
                s["cost_complete"] = False
            else:
                s["cost_usd"] = round(s["cost_usd"] + c.cost_usd, 6)
        return stages

    def _totals(self, stages: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        total_cost = 0.0
        cost_complete = True
        totals = {
            "calls": 0,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
        }
        for s in stages.values():
            for k in totals:
                totals[k] += s[k]
            total_cost = round(total_cost + s["cost_usd"], 6)
            cost_complete = cost_complete and s["cost_complete"]
        totals["cost_usd"] = total_cost
        totals["cost_complete"] = cost_complete
        return totals

    def to_dict(self) -> Dict[str, Any]:
        stages = self._aggregate()
        return {
            "session_id": self.session_id,
            "model": self.model,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "currency": "USD",
            "pricing_note": (
                "Costs computed from cost_tracker.MODEL_PRICING (USD per 1M tokens). "
                "Entries with pricing_verified=false are estimates — confirm against "
                "OpenAI's pricing page."
            ),
            "totals": self._totals(stages),
            "stages": stages,
            "calls": [vars(c) for c in self.calls],
        }

    # ── Output ───────────────────────────────────────────────────────────────

    def write(self, out_dir: Path) -> None:
        """Write llm_cost.json + llm_cost.txt into the session dir. Never raises."""
        try:
            data = self.to_dict()
            out_dir = Path(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "llm_cost.json").write_text(json.dumps(data, indent=2))
            (out_dir / "llm_cost.txt").write_text(self._render_text(data))
        except Exception:  # pragma: no cover - accounting must never break a run
            pass

    @staticmethod
    def _render_text(data: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append("LLM COST REPORT")
        lines.append(f"session : {data['session_id']}")
        lines.append(f"model   : {data['model']}")
        lines.append(f"at      : {data['generated_at']}  ({data['currency']})")
        lines.append("")
        header = f"{'stage':<26}{'calls':>6}{'in':>10}{'cached':>9}{'out':>10}{'reason':>8}{'cost $':>12}"
        lines.append(header)
        lines.append("-" * len(header))
        for stage, s in data["stages"].items():
            cost = f"{s['cost_usd']:.6f}" + ("" if s["cost_complete"] else "*")
            lines.append(
                f"{stage:<26}{s['calls']:>6}{s['input_tokens']:>10}"
                f"{s['cached_input_tokens']:>9}{s['output_tokens']:>10}"
                f"{s['reasoning_tokens']:>8}{cost:>12}"
            )
        lines.append("-" * len(header))
        t = data["totals"]
        tcost = f"{t['cost_usd']:.6f}" + ("" if t["cost_complete"] else "*")
        lines.append(
            f"{'TOTAL':<26}{t['calls']:>6}{t['input_tokens']:>10}"
            f"{t['cached_input_tokens']:>9}{t['output_tokens']:>10}"
            f"{t['reasoning_tokens']:>8}{tcost:>12}"
        )
        if not t["cost_complete"]:
            lines.append("")
            lines.append("* cost incomplete: pricing not configured for one or more models "
                         "(see cost_tracker.MODEL_PRICING).")
        return "\n".join(lines) + "\n"
