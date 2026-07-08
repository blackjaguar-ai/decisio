import json
import logging
import uuid
from fastapi import APIRouter, HTTPException
from app.api.schemas import DecisionRequest, DecisionResponse
from app.graph.graph import run_decision
from app.db import connection as db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/decision/{decision_id}")
async def get_decision_status(decision_id: str):
    """
    Semana 2 — polling para la vista cliente mientras espera resolución
    humana. La vista agente resuelve con POST /cases/{id}/resolve; este
    endpoint es cómo el cliente se entera de que ya se resolvió, sin acoplar
    la app a un websocket (fuera de alcance de la demo — ver Roadmap §0).
    """
    row = await db.fetch_one("SELECT * FROM decisions WHERE id = %s", (decision_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Decisión no encontrada")

    return {
        "decision_id":     decision_id,
        "outcome":         row["final_outcome"],
        "approved_amount": float(row["approved_amount"]) if row["approved_amount"] is not None else None,
        "notice_type":     row["notice_type"],
        "decided_by":      row["decided_by"],
        "route":           row["route"],
        "explanation":     row["explanation"] or {},
        "resolved_at":     row["resolved_at"].isoformat() if row["resolved_at"] else None,
    }


@router.post("/decision", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest):
    # Gate de identidad transaccional (§6.bis). Vive antes del grafo, no es un
    # nodo — si falla, el grafo NUNCA corre y no se toca el core.
    if not request.identity_verified:
        blocked_id = f"blocked-{uuid.uuid4()}"
        logger.warning("POST /decision | %s | identity verification failed, graph not invoked", blocked_id)
        return DecisionResponse(
            decision_id=blocked_id,
            outcome="identity_verification_failed",
            approved_amount=None,
            notice_type=None,
            persisted=True,  # nada que persistir — nunca se ejecutó ninguna operación
            explanation={"summary": "Verificación de identidad fallida. No se ejecutó ninguna operación."},
            latency_ms=None,
            route="blocked",
            guardrail_flags=[],
            trace=[{"step": "identity_gate", "status": "failed"}],
        )

    # Fix #8 — idempotencia: si ya se procesó esta idempotency_key, se devuelve la
    # respuesta ya calculada sin re-correr el grafo (evita ejecutar la ampliación
    # dos veces ante un retry de red del frontend).
    if request.idempotency_key:
        try:
            cached = await db.fetch_one(
                "SELECT response_json FROM decisions WHERE idempotency_key = %s",
                (request.idempotency_key,),
            )
        except Exception as e:
            logger.error("POST /decision | error consultando idempotency_key: %s", e)
            cached = None

        if cached and cached.get("response_json"):
            logger.info("POST /decision | idempotency_key=%s | cache hit", request.idempotency_key)
            return DecisionResponse(**cached["response_json"])

    try:
        result = await run_decision(
            request.customer.model_dump(),
            request.offer.model_dump(),
            request.selected_amount,
        )

        if request.idempotency_key:
            try:
                await db.execute(
                    "UPDATE decisions SET idempotency_key = %s, response_json = %s WHERE id = %s",
                    (request.idempotency_key, json.dumps(result, default=str), result["decision_id"]),
                )
            except Exception as e:
                # No falla la request por esto — la decisión ya se tomó y persistió
                # en `decisions`/`traces`/`metrics`; solo el cacheo de idempotencia falló.
                logger.error("POST /decision | %s | error guardando idempotency_key: %s",
                            result["decision_id"], e)

        return DecisionResponse(**result)
    except Exception as e:
        logger.error("POST /decision | error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
