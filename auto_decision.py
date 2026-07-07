import logging
from datetime import datetime, timezone
from app.graph.state import CreditState

logger = logging.getLogger(__name__)


def auto_decision_node(state: CreditState) -> dict:
    rules_result = state["rules_result"]
    customer     = state["customer"]
    outcome      = rules_result.get("outcome", "rejected")

    final_decision = {
        "outcome": "approved" if outcome == "approved" else "rejected",
        "approved_amount": customer.get("requested_amount") if outcome == "approved" else None,
        "decided_by": "auto",
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("auto_decision | %s | outcome=%s | amount=%s",
                state["decision_id"], final_decision["outcome"], final_decision.get("approved_amount"))

    return {
        "final_decision": final_decision,
        "trace": state["trace"] + [{"step": "auto_decision",
                                    "outcome": final_decision["outcome"], "decided_by": "auto"}],
    }
