from fastapi import APIRouter
from app.db import connection as db

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    totals = await db.fetch_one(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN final_outcome = 'approved'      THEN 1 ELSE 0 END) as approved,
            SUM(CASE WHEN final_outcome = 'rejected'      THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN final_outcome = 'pending_human' THEN 1 ELSE 0 END) as pending_human
        FROM decisions
        """
    )
    latency = await db.fetch_one(
        """
        SELECT
            AVG(latency_ms)                                          as avg_ms,
            MIN(latency_ms)                                          as min_ms,
            MAX(latency_ms)                                          as max_ms,
            AVG(CASE WHEN path = 'auto_approved'   THEN latency_ms END) as avg_auto_ms,
            AVG(CASE WHEN path = 'human_escalated' THEN latency_ms END) as avg_human_ms
        FROM metrics
        """
    )
    path_dist = await db.fetch_all(
        "SELECT path, COUNT(*) as count FROM metrics GROUP BY path ORDER BY count DESC"
    )

    return {
        "totals": {
            "total":        totals["total"] or 0,
            "approved":     totals["approved"] or 0,
            "rejected":     totals["rejected"] or 0,
            "pending_human":totals["pending_human"] or 0,
        },
        "latency_ms": {
            "avg":              round(float(latency["avg_ms"] or 0), 1),
            "min":              latency["min_ms"] or 0,
            "max":              latency["max_ms"] or 0,
            "avg_auto":         round(float(latency["avg_auto_ms"] or 0), 1),
            "avg_human_escalation": round(float(latency["avg_human_ms"] or 0), 1),
        },
        "path_distribution": {r["path"]: r["count"] for r in path_dist},
    }
