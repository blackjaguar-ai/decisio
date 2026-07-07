import json
import logging
import time
from datetime import datetime, timezone
from app.graph.state import CreditState
from app.db import connection as db

logger = logging.getLogger(__name__)


async def finalize_node(state: CreditState) -> dict:
    decision_id    = state["decision_id"]
    final_decision = state.get("final_decision", {})
    customer       = state["customer"]
    trace          = state["trace"]
    route          = state.get("route", "auto")

    if not final_decision:
        final_decision = {"outcome": "pending_human", "approved_amount": None,
                          "decided_by": "human_pending",
                          "decided_at": datetime.now(timezone.utc).isoformat()}

    latency_ms     = int((time.time() - state.get("started_at", time.time())) * 1000)
    outcome        = final_decision.get("outcome", "unknown")
    approved_amount= final_decision.get("approved_amount")
    decided_by     = final_decision.get("decided_by", "auto")

    path_map = {"approved": "auto_approved", "rejected": "auto_rejected",
                "pending_human": "human_escalated"}
    path = path_map.get(outcome, "unknown")

    try:
        await db.execute(
            """
            INSERT INTO decisions (id, customer_id, route, final_outcome, approved_amount, decided_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                final_outcome = EXCLUDED.final_outcome,
                approved_amount = EXCLUDED.approved_amount,
                resolved_at = NOW(),
                decided_by = EXCLUDED.decided_by
            """,
            (decision_id, customer.get("customer_id", "unknown"),
             route, outcome, approved_amount, decided_by),
        )
        for step in trace:
            await db.execute(
                "INSERT INTO traces (decision_id, step, payload) VALUES (%s, %s, %s)",
                (decision_id, step.get("step", "unknown"), json.dumps(step)),
            )
        await db.execute(
            "INSERT INTO metrics (decision_id, path, latency_ms) VALUES (%s, %s, %s)",
            (decision_id, path, latency_ms),
        )
    except Exception as e:
        logger.error("finalize | %s | db error: %s", decision_id, e)

    logger.info("finalize | %s | outcome=%s | latency=%dms | route=%s",
                decision_id, outcome, latency_ms, route)

    return {
        "final_decision": {**final_decision, "latency_ms": latency_ms},
        "trace": trace + [{"step": "finalize", "outcome": outcome,
                           "latency_ms": latency_ms, "decided_by": decided_by}],
    }
