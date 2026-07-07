import os
import logging
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

SCORE_THRESHOLD   = int(os.getenv("CREDIT_SCORE_THRESHOLD", "650"))
MAX_DTI           = float(os.getenv("MAX_DTI_RATIO", "0.40"))
MAX_DTI_GRAY      = float(os.getenv("MAX_DTI_GRAY_ZONE", "0.50"))
MIN_TENURE_MONTHS = int(os.getenv("MIN_TENURE_MONTHS", "6"))
HIGH_AMOUNT       = float(os.getenv("HIGH_AMOUNT_THRESHOLD", "10000"))


def _tenure(c: dict) -> dict | None:
    v = c.get("tenure_months", 0)
    if v < MIN_TENURE_MONTHS:
        return {"rule": "tenure", "outcome": "rejected",
                "reason": f"Antigüedad {v}m < mínimo {MIN_TENURE_MONTHS}m",
                "value": v, "threshold": MIN_TENURE_MONTHS}


def _dti(c: dict) -> dict | None:
    v = c.get("dti_ratio", 0.0)
    if v > MAX_DTI_GRAY:
        return {"rule": "dti", "outcome": "rejected",
                "reason": f"DTI {v:.0%} > límite duro {MAX_DTI_GRAY:.0%}",
                "value": v, "threshold": MAX_DTI_GRAY}
    if v > MAX_DTI:
        return {"rule": "dti", "outcome": "gray_zone",
                "reason": f"DTI {v:.0%} en zona gris ({MAX_DTI:.0%}–{MAX_DTI_GRAY:.0%})",
                "value": v, "threshold": MAX_DTI}


def _payment(c: dict) -> dict | None:
    v = c.get("max_days_overdue_12m", 0)
    if v > 30:
        return {"rule": "payment_behavior", "outcome": "rejected",
                "reason": f"Mora {v}d en últimos 12m (límite: 30d)",
                "value": v, "threshold": 30}
    if v > 0:
        return {"rule": "payment_behavior", "outcome": "gray_zone",
                "reason": f"Mora leve: {v}d en últimos 12m",
                "value": v, "threshold": 0}


def _score(c: dict) -> dict | None:
    v = c.get("credit_score", 0)
    if v < SCORE_THRESHOLD:
        return {"rule": "credit_score", "outcome": "rejected",
                "reason": f"Score {v} < umbral {SCORE_THRESHOLD}",
                "value": v, "threshold": SCORE_THRESHOLD}


def _amount(c: dict) -> dict | None:
    req = c.get("requested_amount", 0)
    pre = c.get("preapproved_limit", 0)
    if req > pre:
        return {"rule": "amount_over_preapproved", "outcome": "human_required",
                "reason": f"S/{req:,.0f} excede tope preaprobado S/{pre:,.0f}",
                "value": req, "threshold": pre}
    if req > HIGH_AMOUNT:
        return {"rule": "high_amount_policy", "outcome": "human_required",
                "reason": f"S/{req:,.0f} supera umbral de alto monto S/{HIGH_AMOUNT:,.0f}",
                "value": req, "threshold": HIGH_AMOUNT}


def rules_engine_node(state: CreditState) -> dict:
    customer = state["customer"]
    triggered: list[dict] = []
    final_outcome = "approved"

    for check in [_tenure, _score, _payment, _dti, _amount]:
        result = check(customer)
        if result is None:
            continue
        triggered.append(result)
        if result["outcome"] == "rejected":
            final_outcome = "rejected"
            break
        elif result["outcome"] == "human_required":
            final_outcome = "human_required"
        elif result["outcome"] == "gray_zone" and final_outcome == "approved":
            final_outcome = "gray_zone"

    rules_result = {
        "outcome": final_outcome,
        "triggered_rules": triggered,
        "all_passed": len(triggered) == 0,
        "requested_amount": customer.get("requested_amount"),
        "preapproved_limit": customer.get("preapproved_limit"),
    }

    logger.info("rules_engine | %s | outcome=%s | triggered=%d",
                state["decision_id"], final_outcome, len(triggered))

    return {
        "rules_result": rules_result,
        "trace": state["trace"] + [{"step": "rules_engine", "outcome": final_outcome,
                                    "triggered_rules": triggered}],
    }
