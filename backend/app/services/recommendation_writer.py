"""
Deterministic template-based natural-language recommendation summary.
No LLM calls — replaceable with an LLM provider in a later phase.

Produces 2–3 short paragraphs regardless of tag count:
  P1 — overview: how many tags matched, compact list of top picks
  P2 — price/lead-time tradeoffs
  P3 — aggregated risk / compliance notes (omitted when none)
"""

from app.services.supplier_matching import MatchResult


def generate_summary(tag_results: dict[str, list[MatchResult]]) -> str:
    if not tag_results:
        return "No window items were available to generate recommendations."

    tag_count = len(tag_results)
    noun = "tag" if tag_count == 1 else "tags"

    # ── Paragraph 1: compact overview ────────────────────────────────────
    top_items: list[str] = []
    for tag, ranked in tag_results.items():
        if ranked:
            top = ranked[0]
            top_items.append(f"{tag}: {top.supplier.name} ({round(top.match_score * 100)}%)")

    p1 = (
        f"Xynect matched {tag_count} window {noun} to supplier options. "
        f"Top {'recommendation' if tag_count == 1 else 'recommendations'}: "
        + "; ".join(top_items) + ". "
        "Scores reflect state availability, opening type, frame material, size range, and supplier reliability."
    )

    # ── Paragraph 2: price/lead-time tradeoffs ────────────────────────────
    alt_notes: list[str] = []
    lead_times_top: list[int] = []

    for tag, ranked in tag_results.items():
        if not ranked:
            continue
        top = ranked[0]
        lead_times_top.append(top.supplier.lead_time_days)
        if len(ranked) >= 2:
            alt = ranked[1]
            if alt.unit_price < top.unit_price * 0.95:
                diff = round((top.unit_price - alt.unit_price) / top.unit_price * 100)
                lead_cmp = (
                    "longer lead time"
                    if alt.supplier.lead_time_days > top.supplier.lead_time_days
                    else "similar lead time"
                )
                alt_notes.append(
                    f"{tag}: {alt.supplier.name} is ~{diff}% cheaper ({lead_cmp})"
                )

    if alt_notes:
        p2 = (
            "Lower-cost alternatives available: "
            + "; ".join(alt_notes)
            + ". See the quote table for full pricing details."
        )
    elif lead_times_top:
        mn, mx = min(lead_times_top), max(lead_times_top)
        if mn == mx:
            p2 = f"Top supplier lead times are {mn} days across all tags."
        else:
            p2 = (
                f"Top supplier lead times range from {mn} to {mx} days. "
                "Review alternative suppliers in the quote table for different price/lead-time tradeoffs."
            )
    else:
        p2 = None

    # ── Paragraph 3: aggregated risks ────────────────────────────────────
    seen: set[str] = set()
    all_risks: list[str] = []
    for ranked in tag_results.values():
        if not ranked or not ranked[0].risk_notes:
            continue
        for risk in ranked[0].risk_notes.split(". "):
            risk = risk.strip().rstrip(".")
            if risk and risk not in seen:
                seen.add(risk)
                all_risks.append(risk)

    p3 = ("Attention: " + ". ".join(all_risks) + ".") if all_risks else None

    paragraphs = [p1]
    if p2:
        paragraphs.append(p2)
    if p3:
        paragraphs.append(p3)

    return "\n\n".join(paragraphs)
