"""
Case explanation — LLM layer (STUB for now, real API key added later).
"""

from app.models.schemas import CaseEvidence


def get_case_explanation(evidence: CaseEvidence) -> str:
    """
    PLACEHOLDER — replace body with a real Gemini/Groq API call later.
    Kept as a deterministic template so the rest of the system can be
    built/demoed without an API key.
    """
    parts = [
        f"Case {evidence.return_id} is flagged with a risk score of "
        f"{evidence.risk_score:.2f} and an expected loss of "
        f"₹{evidence.expected_loss:,.0f} on a refund of ₹{evidence.refund_amount:,.0f}."
    ]

    if evidence.cluster_info.cluster_size > 1:
        parts.append(
            f"This user is linked to {evidence.cluster_info.cluster_size - 1} "
            f"other account(s) via shared device/address/payment identifiers "
            f"(cluster density {evidence.cluster_info.cluster_density:.2f})."
        )
    else:
        parts.append("No shared device/address/payment links were found for this user.")

    if evidence.shared_payment_method_count > 0:
        parts.append(
            f"Notably, {evidence.shared_payment_method_count} other account(s) "
            f"share this user's payment method — a strong structural signal."
        )

    parts.append(
        f"Behaviorally, this user's 30-day return rate is "
        f"{evidence.return_rate_30d*100:.0f}%, which alone is "
        f"{'a strong' if evidence.return_rate_30d > 0.5 else 'not a definitive'} "
        f"signal on its own."
    )

    parts.append(f"Recommended action: {evidence.decision_tier.replace('_', ' ')}.")

    return " ".join(parts)