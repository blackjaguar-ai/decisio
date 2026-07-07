"""
human_in_loop — Semana 1: persiste el caso como pending_human.
Semana 2: esta función se reemplaza con interrupt() de LangGraph + AsyncPostgresSaver.
El resto del grafo no cambia.
"""

import logging
from app.graph.state import CreditState
from app.db import connection as db

logger = logging.getLogger(__name__)


async def human_in_loop_node(state: CreditState) -> dict:
    decision_id   = state["decision_id"]
    customer      = state["customer"]
    rules_result  = state["rules_result"]
    ai_assessment = state.get("ai_assessment", {})

    # Persistir el caso en la bandeja de agentes
    escalation_reason = "; ".join(
        r.get("reason", "") for r in rules_result.get("triggered_rules", [])
    ) or "Escalamiento por política de monto"

    try:
        await db.execute(
            """
            INSERT INTO cases (id, decision_id, status, ai_summary, ai_recommendation,
                               ai_confidence, escalation_reason)
            VALUES (%s, %s, 'pending', %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                decision_id,
                decision_id,
                ai_assessment.get("reasoning"),
                ai_assessment.get("recommendation"),
                ai_assessment.get("confidence"),
                escalation_reason,
            ),
        )
    except Exception as e:
        logger.error("human_in_loop | %s | error persisting case: %s", decision_id, e)

    logger.info("human_in_loop | %s | escalated | reason: %s", decision_id, escalation_reason[:80])

    return {
        "final_decision": {
            "outcome": "pending_human",
            "approved_amount": None,
            "decided_by": "human_pending",
        },
        "trace": state["trace"] + [{"step": "human_in_loop",
                                    "status": "escalated",
                                    "escalation_reason": escalation_reason}],
    }
