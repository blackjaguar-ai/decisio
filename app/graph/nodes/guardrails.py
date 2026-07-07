import logging
import os
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

HIGH_AMOUNT             = float(os.getenv("HIGH_AMOUNT_THRESHOLD", "10000"))
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.70"))


def guardrails_node(state: CreditState) -> dict:
    customer      = state["customer"]
    rules_result  = state["rules_result"]
    ai_assessment = state.get("ai_assessment", {})
    flags: list[dict] = []
    force_human = False

    # G1 — Límite duro de monto
    req = customer.get("requested_amount", 0)
    pre = customer.get("preapproved_limit", 0)
    if req > pre:
        flags.append({"guardrail": "amount_over_limit", "severity": "hard",
                      "message": f"S/{req:,.0f} excede tope preaprobado S/{pre:,.0f}. AI no puede aprobar sobre el tope."})
        force_human = True

    # G2 — Conflicto regla-AI
    if rules_result.get("outcome") == "rejected" and ai_assessment.get("recommendation") == "approve":
        flags.append({"guardrail": "rule_ai_conflict", "severity": "hard",
                      "message": "Reglas dicen RECHAZO, AI recomienda APROBAR. Escalamiento forzado."})
        force_human = True

    # G3 — Confianza mínima
    confidence = ai_assessment.get("confidence", 1.0)
    if ai_assessment and confidence < AI_CONFIDENCE_THRESHOLD:
        flags.append({"guardrail": "low_ai_confidence", "severity": "soft",
                      "message": f"Confianza AI {confidence:.0%} bajo umbral {AI_CONFIDENCE_THRESHOLD:.0%}. DS 115-2025-PCM exige supervisión humana."})
        force_human = True

    # G4 — Inputs anómalos
    anomalies = []
    if customer.get("dti_ratio", 0) < 0:        anomalies.append("dti_ratio negativo")
    if customer.get("credit_score", 500) > 999:  anomalies.append("credit_score fuera de rango")
    if customer.get("requested_amount", 0) <= 0: anomalies.append("monto solicitado <= 0")
    if customer.get("tenure_months", 0) < 0:     anomalies.append("antigüedad negativa")
    if anomalies:
        flags.append({"guardrail": "anomalous_inputs", "severity": "hard",
                      "message": f"Inputs inconsistentes: {', '.join(anomalies)}."})
        force_human = True

    current_route = state.get("route", "auto")
    final_route = "human" if (force_human or current_route == "human") else "auto"

    if flags:
        logger.warning("guardrails | %s | flags=%d | force_human=%s",
                       state["decision_id"], len(flags), force_human)
    else:
        logger.info("guardrails | %s | all_clear | route=%s", state["decision_id"], final_route)

    return {
        "guardrail_flags": flags,
        "route": final_route,
        "trace": state["trace"] + [{"step": "guardrails", "flags": flags, "route": final_route}],
    }
