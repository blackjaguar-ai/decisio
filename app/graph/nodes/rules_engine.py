"""
rules_engine — motor de REVALIDACIÓN, no de evaluación.

No decide si el cliente califica para crédito (eso ya lo decidió el modelo
interno de iO en el batch que generó la oferta). Re-chequea los mismos
criterios contra el estado ACTUAL del cliente, comparando siempre contra
`offer.criteria_snapshot` — la versión de política congelada al momento
del batch — nunca contra ninguna política "vigente" hoy.

El monto NO aparece en ninguna regla de este nodo. El monto es un bound de
la oferta y se valida en `guardrails`, no aquí — no es un criterio de riesgo.
"""

import logging
from app.graph.state import CreditState

logger = logging.getLogger(__name__)


def _tenure(customer: dict, snapshot: dict) -> dict | None:
    min_tenure = snapshot.get("min_tenure_months", 6)
    v = customer.get("tenure_months", 0)
    if v < min_tenure:
        return {"rule": "tenure", "outcome": "hallazgo_descalificante",
                "reason": f"Antigüedad {v}m < mínimo congelado {min_tenure}m",
                "value": v, "threshold": min_tenure}
    return None


def _score(customer: dict, snapshot: dict) -> dict | None:
    threshold = snapshot.get("score_threshold", 650)
    v = customer.get("credit_score", 0)
    if v < threshold:
        return {"rule": "credit_score", "outcome": "hallazgo_descalificante",
                "reason": f"Score cayó a {v}, bajo el umbral congelado {threshold} desde el batch",
                "value": v, "threshold": threshold}
    return None


def _payment(customer: dict, snapshot: dict) -> dict | None:
    v = customer.get("max_days_overdue_12m", 0)
    if v > 30:
        return {"rule": "payment_behavior", "outcome": "hallazgo_descalificante",
                "reason": f"Mora de {v}d posterior al batch (límite congelado: 30d)",
                "value": v, "threshold": 30}
    if v > 0:
        return {"rule": "payment_behavior", "outcome": "hallazgo_menor",
                "reason": f"Mora leve de {v}d posteada después del batch",
                "value": v, "threshold": 0}
    return None


def _dti(customer: dict, snapshot: dict) -> dict | None:
    max_dti = snapshot.get("max_dti", 0.40)
    max_dti_gray = snapshot.get("max_dti_gray", 0.50)
    v = customer.get("dti_ratio", 0.0)
    if v > max_dti_gray:
        return {"rule": "dti", "outcome": "hallazgo_descalificante",
                "reason": f"DTI {v:.0%} > límite duro congelado {max_dti_gray:.0%}",
                "value": v, "threshold": max_dti_gray}
    if v > max_dti:
        return {"rule": "dti", "outcome": "hallazgo_menor",
                "reason": f"DTI {v:.0%} subió sobre el criterio congelado ({max_dti:.0%}) desde el batch",
                "value": v, "threshold": max_dti}
    return None


def _account_status(customer: dict, snapshot: dict) -> dict | None:
    status = customer.get("account_status", "active")
    if status in ("blocked", "fraud_confirmed", "closed"):
        return {"rule": "account_status", "outcome": "hallazgo_descalificante",
                "reason": f"Estado de cuenta '{status}' detectado posterior al batch",
                "value": status, "threshold": "active"}
    if customer.get("data_inconsistency"):
        return {"rule": "account_status", "outcome": "hallazgo_menor",
                "reason": "Inconsistencia entre snapshot del batch y estado actual del core",
                "value": True, "threshold": False}
    return None


def rules_engine_node(state: CreditState) -> dict:
    customer = state["customer"]
    snapshot = state["offer"].get("criteria_snapshot", {})
    triggered: list[dict] = []
    final_outcome = "sin_cambios"

    for check in [_tenure, _score, _payment, _dti, _account_status]:
        result = check(customer, snapshot)
        if result is None:
            continue
        triggered.append(result)
        if result["outcome"] == "hallazgo_descalificante":
            final_outcome = "hallazgo_descalificante"
            break
        elif result["outcome"] == "hallazgo_menor" and final_outcome == "sin_cambios":
            final_outcome = "hallazgo_menor"

    revalidation_result = {
        "outcome": final_outcome,
        "triggered_rules": triggered,
        "all_passed": len(triggered) == 0,
        "rules_version_used": state["offer"].get("rules_version"),
    }

    logger.info("rules_engine | %s | outcome=%s | triggered=%d | rules_version=%s",
                state["decision_id"], final_outcome, len(triggered), state["offer"].get("rules_version"))

    return {
        "revalidation_result": revalidation_result,
        "trace": state["trace"] + [{"step": "rules_engine", "outcome": final_outcome,
                                    "triggered_rules": triggered,
                                    "rules_version_used": state["offer"].get("rules_version")}],
    }
