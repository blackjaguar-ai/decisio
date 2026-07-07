"""
cases — Semana 2.
GET  /cases              → bandeja de agentes
POST /cases/{id}/resolve → reanuda el grafo con la resolución humana
"""

from fastapi import APIRouter
from app.db import connection as db

router = APIRouter()


@router.get("/cases")
async def list_cases():
    cases = await db.fetch_all(
        """
        SELECT id, decision_id, status, ai_summary, ai_recommendation,
               ai_confidence, escalation_reason, created_at
        FROM cases
        WHERE status = 'pending'
        ORDER BY created_at DESC
        """,
    )
    return {"cases": cases}
