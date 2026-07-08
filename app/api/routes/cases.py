"""
cases — Semana 2 (real).
GET  /cases               → bandeja de agentes (casos pendientes, con contexto)
GET  /cases/{id}          → detalle de un caso (perfil + oferta + AI, para la vista agente)
POST /cases/{id}/resolve  → reanuda el grafo con la resolución humana vía
                            interrupt()/Command(resume=...)
"""

import logging
from fastapi import APIRouter, HTTPException
from app.api.schemas import CaseResolutionRequest, DecisionResponse
from app.db import connection as db
from app.graph.graph import resolve_case

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/cases")
async def list_cases():
    cases = await db.fetch_all(
        """
        SELECT id, decision_id, status, ai_summary, ai_recommendation,
               ai_confidence, escalation_reason, context, created_at
        FROM cases
        WHERE status = 'pending'
        ORDER BY created_at ASC
        """,
    )
    return {"cases": cases}


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    case = await db.fetch_one("SELECT * FROM cases WHERE id = %s", (case_id,))
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    decision = await db.fetch_one("SELECT * FROM decisions WHERE id = %s", (case_id,))
    return {"case": case, "decision": decision}


@router.post("/cases/{case_id}/resolve", response_model=DecisionResponse)
async def resolve(case_id: str, request: CaseResolutionRequest):
    case = await db.fetch_one("SELECT status FROM cases WHERE id = %s", (case_id,))
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    if case["status"] != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Caso ya resuelto (status={case['status']}) — no se puede reanudar dos veces.",
        )

    try:
        result = await resolve_case(case_id, request.model_dump())
    except RuntimeError as e:
        logger.error("POST /cases/%s/resolve | %s", case_id, e)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("POST /cases/%s/resolve | error inesperado: %s", case_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al resolver el caso.")

    return DecisionResponse(**result)
