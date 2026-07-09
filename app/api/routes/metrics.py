"""
metrics — Semana 3: extendido para el dashboard de observabilidad (Roadmap
Día 18-19, Spec §7).

Lo que se agregó sobre la versión de Semana 1:
- `identity_blocked`: el gate de identidad (§6.bis) ahora se loguea en
  `metrics` (ver decision.py) — antes era invisible aquí.
- `guardrail_counts`: cuenta cuántas veces se disparó cada guardrail
  (staleness, tampering, coherencia regla-AI, confianza mínima), leyendo
  `traces` donde step='guardrails' o 'bounds_check'. Responde en vivo la
  pregunta de un CTO: "¿el guardrail alguna vez actuó, o es teatro?".
- `human_resolutions`: desglose honor/adjust/revoke de `cases` resueltos —
  muestra que el humano tiene poder real de decisión, no solo de aprobar.
- `recent`: últimas N decisiones con latencia real medida (`latency_ms`,
  medido con time.time() en finalize.py — nunca simulado) para el gráfico
  de tendencia y el feed en vivo. Esto es lo que hace el cronómetro de la
  demo defendible: no es "8 segundos" de marketing, es el promedio real de
  lo que ya se corrió.
"""

from fastapi import APIRouter
from app.db import connection as db

router = APIRouter()


@router.get("/metrics")
async def get_metrics():
    totals = await db.fetch_one(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN final_outcome = 'honored'       THEN 1 ELSE 0 END) as honored,
            SUM(CASE WHEN final_outcome = 'revoked'       THEN 1 ELSE 0 END) as revoked,
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
            AVG(CASE WHEN path IN ('auto_honored', 'auto_revoked')
                     THEN latency_ms END)                            as avg_auto_ms,
            AVG(CASE WHEN path = 'human_escalated' THEN latency_ms END) as avg_human_ms,
            COUNT(*) FILTER (WHERE path IN ('auto_honored', 'auto_revoked')) as n_auto,
            COUNT(*) FILTER (WHERE path = 'human_escalated')              as n_human
        FROM metrics
        WHERE path != 'identity_blocked'
        """
    )
    path_dist = await db.fetch_all(
        "SELECT path, COUNT(*) as count FROM metrics GROUP BY path ORDER BY count DESC"
    )
    identity_blocked = await db.fetch_one(
        "SELECT COUNT(*) as count FROM metrics WHERE path = 'identity_blocked'"
    )

    # Guardrails disparados — lee traces del nodo guardrails/bounds_check,
    # cada flag trae {"guardrail": "...", "severity": "hard"|"soft", "message": "..."}.
    guardrail_rows = await db.fetch_all(
        """
        SELECT payload -> 'flags' as flags
        FROM traces
        WHERE step IN ('guardrails', 'bounds_check')
          AND jsonb_array_length(COALESCE(payload -> 'flags', '[]'::jsonb)) > 0
        """
    )
    guardrail_counts: dict[str, int] = {}
    for row in guardrail_rows:
        for flag in (row["flags"] or []):
            name = flag.get("guardrail", "unknown")
            guardrail_counts[name] = guardrail_counts.get(name, 0) + 1

    # Desglose de resoluciones humanas (honor / adjust / revoke).
    resolution_rows = await db.fetch_all(
        """
        SELECT resolution, COUNT(*) as count
        FROM cases
        WHERE status = 'resolved' AND resolution IS NOT NULL
        GROUP BY resolution
        """
    )
    human_resolutions = {r["resolution"]: r["count"] for r in resolution_rows}

    # Semana 3: el nombre del agente (resolved_by) no aparecía agregado en
    # ningún lado del dashboard — solo enterrado en la columna "decidido
    # por" del feed crudo, con el prefijo interno "human:" sin limpiar.
    # Este desglose responde directo "¿quién está resolviendo los casos?".
    agent_rows = await db.fetch_all(
        """
        SELECT resolved_by, COUNT(*) as count
        FROM cases
        WHERE status = 'resolved' AND resolved_by IS NOT NULL
        GROUP BY resolved_by
        ORDER BY count DESC
        """
    )
    agent_activity = {r["resolved_by"]: r["count"] for r in agent_rows}

    pending_cases = await db.fetch_one(
        "SELECT COUNT(*) as count FROM cases WHERE status = 'pending'"
    )

    # Feed reciente — para el gráfico de tendencia de latencia y la lista en
    # vivo del dashboard. Solo decisiones ya finalizadas (con latencia real).
    recent = await db.fetch_all(
        """
        SELECT d.id, d.final_outcome, d.route, d.decided_by, d.created_at,
               d.approved_amount, m.path, m.latency_ms
        FROM decisions d
        LEFT JOIN metrics m ON m.decision_id = d.id AND m.path != 'identity_blocked'
        ORDER BY d.created_at DESC
        LIMIT 30
        """
    )

    total = totals["total"] or 0
    human_touched = (totals["pending_human"] or 0) + sum(human_resolutions.values())

    return {
        "totals": {
            "total":            total,
            "honored":          totals["honored"] or 0,
            "revoked":          totals["revoked"] or 0,
            "pending_human":    totals["pending_human"] or 0,
            "identity_blocked": identity_blocked["count"] or 0,
        },
        "latency_ms": {
            # ADVERTENCIA (Semana 3, post-fix): `avg` mezcla TODOS los caminos,
            # incluyendo `human_escalated` — cuyo tiempo real incluye cuánto
            # tardó el agente en resolver, no la latencia del motor. NUNCA usar
            # este campo para el ring/hero de "camino limpio" del dashboard —
            # usar `avg_auto`, que excluye toda espera humana. Se conserva aquí
            # solo como cifra informativa de "latencia global observada".
            "avg":                  round(float(latency["avg_ms"] or 0), 1),
            "min":                  latency["min_ms"] or 0,
            "max":                  latency["max_ms"] or 0,
            "avg_auto":             round(float(latency["avg_auto_ms"] or 0), 1),
            "avg_human_escalation": round(float(latency["avg_human_ms"] or 0), 1),
            "n_auto":               latency["n_auto"] or 0,
            "n_human":              latency["n_human"] or 0,
        },
        "path_distribution": {r["path"]: r["count"] for r in path_dist},
        "guardrail_counts": guardrail_counts,
        "human_resolutions": human_resolutions,
        "agent_activity": agent_activity,
        "pending_cases_now": pending_cases["count"] or 0,
        "human_intervention_rate": round(human_touched / total, 4) if total else 0.0,
        "recent": [
            {
                "decision_id":     r["id"],
                "outcome":         r["final_outcome"],
                "route":           r["route"],
                # "human:agente_x" -> "agente_x" — el prefijo es convención
                # interna de human_in_loop.py, no algo que un CTO deba leer.
                "decided_by":      (r["decided_by"] or "").removeprefix("human:") or None,
                "path":            r["path"],
                "latency_ms":      r["latency_ms"],
                "approved_amount": float(r["approved_amount"]) if r["approved_amount"] is not None else None,
                "created_at":      r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in recent
        ],
    }
