"""
Deterministic template-based natural-language recommendation summary.
No LLM calls — replaceable with an LLM provider in a later phase.
"""

from app.services.supplier_matching import MatchResult


def _tag_paragraph(tag: str, ranked: list[MatchResult]) -> str:
    if not ranked:
        return f"No supplier recommendations could be generated for tag {tag}."

    top = ranked[0]
    lines: list[str] = []

    # Lead sentence
    lines.append(
        f"For tag {tag}, {top.supplier.name} is the top recommendation "
        f"(match score: {round(top.match_score * 100)}%). "
        f"{top.match_reason}"
    )

    # Alternatives
    if len(ranked) >= 2:
        alt = ranked[1]
        price_diff = alt.unit_price - top.unit_price
        price_note = (
            f"at a lower unit price (${alt.unit_price:.0f} vs ${top.unit_price:.0f})"
            if price_diff < 0
            else f"at a higher unit price (${alt.unit_price:.0f} vs ${top.unit_price:.0f})"
        )
        alt_lead = alt.supplier.lead_time_days
        top_lead = top.supplier.lead_time_days
        lead_note = (
            f"shorter lead time ({alt_lead} days)"
            if alt_lead < top_lead
            else f"longer lead time ({alt_lead} days)"
        )
        lines.append(
            f"{alt.supplier.name} is an alternative {price_note} "
            f"and {lead_note}."
        )

    if len(ranked) >= 3:
        third = ranked[2]
        lines.append(
            f"{third.supplier.name} is also available "
            f"(match score: {round(third.match_score * 100)}%, "
            f"lead time: {third.supplier.lead_time_days} days)."
        )

    # Risk notes from top recommendation
    if top.risk_notes:
        lines.append(f"Important: {top.risk_notes}")

    return " ".join(lines)


def generate_summary(tag_results: dict[str, list[MatchResult]]) -> str:
    if not tag_results:
        return "No window items were available to generate recommendations."

    paragraphs = [_tag_paragraph(tag, ranked) for tag, ranked in tag_results.items()]
    header = (
        f"Xynect found supplier matches for {len(tag_results)} "
        f"window {'tag' if len(tag_results) == 1 else 'tags'}. "
        "Review the quote table above for detailed pricing and lead times. "
        "Scores are based on state, opening type, frame material, size range, and supplier reliability."
    )
    return header + "\n\n" + "\n\n".join(paragraphs)
