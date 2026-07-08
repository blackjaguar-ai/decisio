import logging
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

REQUIRED_CUSTOMER_FIELDS = [
    "customer_id", "credit_score", "tenure_months",
    "dti_ratio", "max_days_overdue_12m",
]
REQUIRED_OFFER_FIELDS = [
    "offer_id", "floor_amount", "cap_at_offer_time",
    "rules_version", "criteria_snapshot",
]


def ingest_node(state: CreditState) -> dict:
    customer = state["customer"]
    offer = state["offer"]

    missing = [f for f in REQUIRED_CUSTOMER_FIELDS if f not in customer]
    missing += [f"offer.{f}" for f in REQUIRED_OFFER_FIELDS if f not in offer]

    try:
        customer["credit_score"]         = int(customer.get("credit_score", 0))
        customer["tenure_months"]        = int(customer.get("tenure_months", 0))
        customer["dti_ratio"]            = float(customer.get("dti_ratio", 0))
        customer["max_days_overdue_12m"] = int(customer.get("max_days_overdue_12m", 0))
        customer["account_status"]       = customer.get("account_status", "active")
        customer["data_inconsistency"]   = bool(customer.get("data_inconsistency", False))

        # offer.rules_version / offer.criteria_snapshot se CARGAN, nunca se recalculan aquí.
        # ingest no tiene autoridad para decidir con qué criterio se revalida — ese criterio
        # ya viene congelado desde el batch que generó la oferta.
        offer["floor_amount"]         = float(offer.get("floor_amount", 0))
        offer["cap_at_offer_time"]    = float(offer.get("cap_at_offer_time", 0))
        offer["cap_at_execution_time"] = float(
            offer.get("cap_at_execution_time") or offer.get("cap_at_offer_time", 0)
        )
    except (ValueError, TypeError) as e:
        missing.append(f"type_error:{e}")

    route = "human" if missing else "auto"

    if missing:
        logger.warning("ingest | %s | missing=%s", state["decision_id"], missing)
    else:
        logger.info("ingest | %s | ok | offer_id=%s | rules_version=%s",
                     state["decision_id"], offer.get("offer_id"), offer.get("rules_version"))

    return {
        "customer": customer,
        "offer": offer,
        "route": route,
        "trace": [{"step": "ingest", "status": "ok" if not missing else "incomplete",
                   "missing_fields": missing, "rules_version": offer.get("rules_version")}],
    }
