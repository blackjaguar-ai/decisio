import logging
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "customer_id", "credit_score", "tenure_months",
    "dti_ratio", "max_days_overdue_12m",
    "requested_amount", "preapproved_limit",
]


def ingest_node(state: CreditState) -> dict:
    customer = state["customer"]
    missing = [f for f in REQUIRED_FIELDS if f not in customer]

    try:
        customer["credit_score"]        = int(customer.get("credit_score", 0))
        customer["tenure_months"]       = int(customer.get("tenure_months", 0))
        customer["dti_ratio"]           = float(customer.get("dti_ratio", 0))
        customer["max_days_overdue_12m"]= int(customer.get("max_days_overdue_12m", 0))
        customer["requested_amount"]    = float(customer.get("requested_amount", 0))
        customer["preapproved_limit"]   = float(customer.get("preapproved_limit", 0))
    except (ValueError, TypeError) as e:
        missing.append(f"type_error:{e}")

    route = "human" if missing else "auto"

    if missing:
        logger.warning("ingest | %s | missing=%s", state["decision_id"], missing)
    else:
        logger.info("ingest | %s | ok", state["decision_id"])

    return {
        "customer": customer,
        "route": route,
        "trace": [{"step": "ingest", "status": "ok" if not missing else "incomplete", "missing_fields": missing}],
    }
