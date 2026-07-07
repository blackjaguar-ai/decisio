from fastapi import APIRouter, HTTPException
from app.db import connection as db

router = APIRouter()


@router.get("/trace/{decision_id}")
async def get_trace(decision_id: str):
    decision = await db.fetch_one("SELECT * FROM decisions WHERE id = %s", (decision_id,))
    if not decision:
        raise HTTPException(status_code=404, detail="Decisión no encontrada")

    traces = await db.fetch_all(
        "SELECT step, payload, ts FROM traces WHERE decision_id = %s ORDER BY ts ASC",
        (decision_id,),
    )

    return {
        "decision_id": decision_id,
        "outcome":     decision["final_outcome"],
        "route":       decision["route"],
        "decided_by":  decision["decided_by"],
        "created_at":  decision["created_at"].isoformat() if decision["created_at"] else None,
        "steps": [{"step": t["step"], "payload": t["payload"],
                   "ts": t["ts"].isoformat() if t["ts"] else None} for t in traces],
    }
