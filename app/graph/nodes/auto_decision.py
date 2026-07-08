import logging
from datetime import datetime, timezone
from app.graph.state import CreditState

logger = logging.getLogger(__name__)


def auto_decision_node(state: CreditState) -> dict:
    revalidation_result = state["revalidation_result"]
    outcome              = revalidation_result.get("outcome", "hallazgo_descalificante")
    selected_amount      = state.get("selected_amount", 0)
    ai_explanation        = state.get("ai_explanation", {})
    notice_type          = ai_explanation.get("notice_type")

    if outcome == "sin_cambios":
        final_outcome   = "honored"
        approved_amount = selected_amount
    else:  # hallazgo_descalificante
        final_outcome   = "revoked"
        approved_amount = None

    final_decision = {
        "outcome": final_outcome,
        "approved_amount": approved_amount,
        "decided_by": "auto",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "notice_type": notice_type if final_outcome == "revoked" else None,
    }

    logger.info("auto_decision | %s | outcome=%s | amount=%s | notice_type=%s",
                state["decision_id"], final_decision["outcome"],
                final_decision.get("approved_amount"), final_decision.get("notice_type"))

    return {
        "final_decision": final_decision,
        "trace": state["trace"] + [{"step": "auto_decision",
                                    "outcome": final_decision["outcome"], "decided_by": "auto",
                                    "notice_type": final_decision.get("notice_type")}],
    }
