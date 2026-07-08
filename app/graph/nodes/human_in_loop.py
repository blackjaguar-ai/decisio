"""
human_in_loop — Semana 2: interrupt() REAL de LangGraph. El grafo se pausa
literalmente (excepción `GraphInterrupt` capturada por el runtime de Pregel) y
el estado queda persistido en Postgres vía `AsyncPostgresSaver`
(app/graph/checkpointer.py) — sobrevive un restart del contenedor `app`,
validado en sandbox antes de escribir este archivo.

Advertencia de LangGraph que condiciona el diseño de abajo: al reanudar con
`Command(resume=...)`, esta función se **re-ejecuta desde el inicio** — todo
el código antes de `interrupt()` corre dos veces (una vez al pausar, otra al
reanudar, esta segunda vez `interrupt()` devuelve el valor de resume en vez de
pausar de nuevo). Por eso:

- Los dos inserts de abajo (`decisions` placeholder, `cases`) son
  `ON CONFLICT DO NOTHING` — no se duplican en la segunda pasada.
- El paso de `trace` de ESTE nodo no se escribe a la tabla `traces` aquí — se
  pospone a `finalize`, que corre una sola vez, después del resume. Escribir
  el trace acá también duplicaría filas en la segunda pasada sin una clave de
  conflicto natural para deduplicarlas (`traces.id` es un `BIGSERIAL` sin
  significado de negocio). Esto es una decisión deliberada, no un olvido: la
  vista "timeline completo por caso" es explícitamente Semana 3 (Roadmap
  Día 19) — mientras el caso está pendiente, la fila de `cases` YA es visible
  en la bandeja del agente con resumen AI y motivo de escalamiento, que es
  toda la visibilidad que Semana 2 promete.

El placeholder en `decisions` (nuevo en esta ronda) existe porque, con
`interrupt()` real, `finalize` YA NO corre en el mismo request que devuelve
`pending_human` al cliente — el grafo está literalmente pausado antes de
llegar ahí. Sin este placeholder, `GET /trace/{id}` devolvería 404 mientras
el caso espera agente, y la idempotencia de `POST /decision` no tendría fila
sobre la cual guardar `idempotency_key`. `finalize` sigue siendo quien
actualiza esa fila con el resultado final (su `INSERT ... ON CONFLICT DO
UPDATE` ya estaba escrito para esto, sin cambios).
"""

import json
import logging
from datetime import datetime, timezone

from langgraph.types import interrupt

from app.db import connection as db
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

VALID_ACTIONS = {"honor", "adjust", "revoke"}


async def human_in_loop_node(state: CreditState) -> dict:
    decision_id = state["decision_id"]
    ai_assessment = state.get("ai_assessment", {})
    revalidation_result = state.get("revalidation_result", {})
    customer = state["customer"]
    offer = state.get("offer", {})
    selected_amount = state.get("selected_amount")

    triggered_reasons = [
        r.get("reason", "") for r in revalidation_result.get("triggered_rules", [])
    ]
    # Fix heredado del refactor anterior: si se llega aquí directo desde ingest
    # (payload incompleto), triggered_reasons está vacío — usar el motivo real.
    if not triggered_reasons:
        ingest_step = next((s for s in state.get("trace", []) if s.get("step") == "ingest"), None)
        if ingest_step and ingest_step.get("missing_fields"):
            triggered_reasons = [f"Payload incompleto: {', '.join(ingest_step['missing_fields'])}"]
    escalation_reason = "; ".join(triggered_reasons) or "Escalamiento por hallazgo en revalidación"

    # ── Placeholder en `decisions` — visible en /trace mientras está pendiente.
    try:
        await db.execute(
            """
            INSERT INTO decisions (id, customer_id, route, final_outcome, offer_id,
                                    rules_version, selected_amount)
            VALUES (%s, %s, 'human', 'pending_human', %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (decision_id, customer.get("customer_id", "unknown"),
             offer.get("offer_id"), offer.get("rules_version"), selected_amount),
        )
    except Exception as e:
        logger.error("human_in_loop | %s | error creando placeholder en decisions: %s", decision_id, e)

    # ── Caso visible en la bandeja del agente (GET /cases), con contexto
    # completo (perfil + oferta) -- lo que el Spec exige que el agente vea.
    try:
        await db.execute(
            """
            INSERT INTO cases (id, decision_id, status, ai_summary, ai_recommendation,
                               ai_confidence, escalation_reason, context)
            VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (
                decision_id, decision_id,
                ai_assessment.get("reasoning"),
                ai_assessment.get("recommendation"),
                ai_assessment.get("confidence"),
                escalation_reason,
                json.dumps({
                    "customer": customer,
                    "offer": offer,
                    "selected_amount": selected_amount,
                }, default=str),
            ),
        )
    except Exception as e:
        logger.error("human_in_loop | %s | error persisting case: %s", decision_id, e)

    logger.info("human_in_loop | %s | interrupting | reason: %s", decision_id, escalation_reason[:80])

    # ─────────────────────── PAUSA REAL DEL GRAFO ───────────────────────────
    # Ejecución detenida aquí hasta que POST /cases/{id}/resolve invoque
    # resolve_case() -> graph.ainvoke(Command(resume=resolution), config).
    # `resolution` es exactamente el body validado por CaseResolutionRequest
    # (app/api/schemas.py), serializado con .model_dump().
    resolution = interrupt({
        "decision_id": decision_id,
        "escalation_reason": escalation_reason,
        "ai_assessment": ai_assessment,
        "customer_id": customer.get("customer_id"),
        "offer_id": offer.get("offer_id"),
        "selected_amount": selected_amount,
    })
    # ─────────────────────────────────────────────────────────────────────

    action = resolution.get("action")
    resolved_by = resolution.get("resolved_by") or "agente_desconocido"
    adjusted_amount = resolution.get("adjusted_amount")

    if action not in VALID_ACTIONS:
        # Defensa en profundidad: un payload de resume corrupto (no debería
        # pasar nunca — CaseResolutionRequest ya lo valida en el borde de la
        # API — pero si algún día alguien llama resolve_case() directo sin
        # pasar por el schema HTTP) nunca debe ejecutar dinero por default.
        # Se trata como revocación segura, igual que un hallazgo duro.
        logger.error("human_in_loop | %s | acción de resolución inválida: %r — se revoca por seguridad",
                    decision_id, action)
        action = "revoke"

    if action == "honor":
        final_outcome = "honored"
        approved_amount = selected_amount
        notice_type = None
    elif action == "adjust":
        final_outcome = "honored"
        # Guardrail de negocio: un agente puede AJUSTAR hacia abajo, nunca
        # inflar por encima de lo que el cliente pidió en el slider — eso
        # requeriría una oferta nueva, no una resolución de HITL.
        if adjusted_amount and 0 < adjusted_amount <= (selected_amount or float("inf")):
            approved_amount = adjusted_amount
        else:
            logger.warning("human_in_loop | %s | adjusted_amount inválido (%s) — se usa selected_amount",
                           decision_id, adjusted_amount)
            approved_amount = selected_amount
        notice_type = None
    else:  # revoke
        final_outcome = "revoked"
        approved_amount = None
        notice_type = "adverse_action"

    final_decision = {
        "outcome": final_outcome,
        "approved_amount": approved_amount,
        "decided_by": f"human:{resolved_by}",
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "notice_type": notice_type,
    }

    try:
        await db.execute(
            """
            UPDATE cases SET status = 'resolved', resolution = %s, resolution_amount = %s,
                             resolved_by = %s, resolved_at = NOW()
            WHERE id = %s
            """,
            (action, approved_amount, resolved_by, decision_id),
        )
    except Exception as e:
        logger.error("human_in_loop | %s | error actualizando case resuelto: %s", decision_id, e)

    logger.info("human_in_loop | %s | resolved | action=%s | by=%s | amount=%s",
               decision_id, action, resolved_by, approved_amount)

    return {
        "final_decision": final_decision,
        "route": "human",
        "trace": state["trace"] + [{"step": "human_in_loop", "status": "resolved",
                                    "escalation_reason": escalation_reason,
                                    "resolution_action": action, "resolved_by": resolved_by}],
    }
