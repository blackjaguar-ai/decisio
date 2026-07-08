"""
finalize — consolida la decisión y escribe el trace completo.

Fix #4: antes, un solo try/except envolvía los 3 inserts (decisions, traces,
metrics); si CUALQUIERA fallaba, se logueaba como error y la API respondía
200 igual, como si todo se hubiera persistido. Para un banco que compra
"trazabilidad de 3 años" como argumento regulatorio (DS 115-2025-PCM / Res.
SBS 053-2023), fallar en persistir el audit trail no puede ser un
`logger.error` que nadie ve del lado del cliente.

Ahora cada insert está en su propio try/except (uno no bloquea a los otros:
si falla `decisions` igual se intenta escribir `traces` y `metrics`), y
`persisted: bool` viaja en la respuesta de la API — si cualquiera de los tres
falló, `persisted=False` y el cliente/frontend puede reaccionar en vez de
asumir que todo quedó guardado.
"""

import json
import logging
import time
from datetime import datetime, timezone
from app.graph.state import CreditState
from app.db import connection as db

logger = logging.getLogger(__name__)


async def finalize_node(state: CreditState) -> dict:
    decision_id     = state["decision_id"]
    final_decision  = state.get("final_decision", {})
    customer        = state["customer"]
    offer           = state.get("offer", {})
    selected_amount = state.get("selected_amount")
    route           = state.get("route", "auto")

    if not final_decision:
        final_decision = {"outcome": "pending_human", "approved_amount": None,
                          "decided_by": "human_pending", "notice_type": None,
                          "decided_at": datetime.now(timezone.utc).isoformat()}

    latency_ms      = int((time.time() - state.get("started_at", time.time())) * 1000)
    outcome         = final_decision.get("outcome", "unknown")
    approved_amount = final_decision.get("approved_amount")
    decided_by      = final_decision.get("decided_by", "auto")
    notice_type     = final_decision.get("notice_type")

    # Construido ANTES del loop de inserts — así finalize se loguea a sí mismo.
    trace = state["trace"] + [{"step": "finalize", "outcome": outcome,
                                "latency_ms": latency_ms, "decided_by": decided_by,
                                "notice_type": notice_type}]

    path_map = {"honored": "auto_honored", "revoked": "auto_revoked",
                "pending_human": "human_escalated"}
    path = path_map.get(outcome, "unknown")

    persisted = True

    try:
        await db.execute(
            """
            INSERT INTO decisions (id, customer_id, route, final_outcome, approved_amount,
                                    decided_by, offer_id, rules_version, selected_amount, notice_type,
                                    explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                final_outcome   = EXCLUDED.final_outcome,
                approved_amount = EXCLUDED.approved_amount,
                decided_by      = EXCLUDED.decided_by,
                notice_type     = EXCLUDED.notice_type,
                explanation     = EXCLUDED.explanation,
                resolved_at     = NOW()
            """,
            (decision_id, customer.get("customer_id", "unknown"), route, outcome,
             approved_amount, decided_by, offer.get("offer_id"), offer.get("rules_version"),
             selected_amount, notice_type, json.dumps(state.get("ai_explanation", {}), default=str)),
        )
    except Exception as e:
        logger.error("finalize | %s | db error insertando decisions: %s", decision_id, e)
        persisted = False

    try:
        for step in trace:  # incluye finalize
            await db.execute(
                "INSERT INTO traces (decision_id, step, payload) VALUES (%s, %s, %s)",
                (decision_id, step.get("step", "unknown"), json.dumps(step)),
            )
    except Exception as e:
        logger.error("finalize | %s | db error insertando traces: %s", decision_id, e)
        persisted = False

    try:
        await db.execute(
            "INSERT INTO metrics (decision_id, path, latency_ms) VALUES (%s, %s, %s)",
            (decision_id, path, latency_ms),
        )
    except Exception as e:
        logger.error("finalize | %s | db error insertando metrics: %s", decision_id, e)
        persisted = False

    if not persisted:
        logger.critical("finalize | %s | DECISIÓN NO PERSISTIDA COMPLETAMENTE — audit trail incompleto",
                        decision_id)

    logger.info("finalize | %s | outcome=%s | latency=%dms | route=%s | persisted=%s",
                decision_id, outcome, latency_ms, route, persisted)

    return {
        "final_decision": {**final_decision, "latency_ms": latency_ms, "persisted": persisted},
        "trace": trace,
    }
