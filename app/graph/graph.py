"""
Grafo LangGraph — DECISIO Motor de Revalidación de Oferta Firme.
3 rutas reales + 1 corte temprano por payload incompleto + 1 gate de
identidad previo (fuera del grafo, ver app/api/routes/decision.py).
"""

import time
import uuid
import logging
from langgraph.graph import StateGraph, END

from app.graph.state import CreditState
from app.graph.nodes.ingest import ingest_node
from app.graph.nodes.bounds_check import bounds_check_node
from app.graph.nodes.rules_engine import rules_engine_node
from app.graph.nodes.ai_assessor import ai_assessor_node
from app.graph.nodes.ai_explainer import ai_explainer_node
from app.graph.nodes.guardrails import guardrails_node
from app.graph.nodes.auto_decision import auto_decision_node
from app.graph.nodes.human_in_loop import human_in_loop_node
from app.graph.nodes.finalize import finalize_node

logger = logging.getLogger(__name__)


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_ingest(state: CreditState) -> str:
    """
    Fix #3: antes, un payload incompleto seguía de largo con ceros silenciosos
    (`.get(campo, 0)`) y podía terminar clasificado como sin_cambios por accidente.
    Ahora, si ingest detectó campos faltantes, se corta directo a human_in_loop —
    nunca se le da a rules_engine un perfil con datos inventados.
    """
    last_step = state["trace"][-1] if state.get("trace") else {}
    if last_step.get("step") == "ingest" and last_step.get("status") == "incomplete":
        return "human_in_loop"
    return "bounds_check"


def route_after_rules(state: CreditState) -> str:
    outcome = state["revalidation_result"].get("outcome", "hallazgo_descalificante")
    if outcome == "hallazgo_menor":
        return "ai_assessor"
    return "ai_explainer"


def route_after_guardrails(state: CreditState) -> str:
    return "human_in_loop" if state.get("route") == "human" else "auto_decision"


# ── Build ──────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(CreditState)

    g.add_node("ingest",        ingest_node)
    g.add_node("bounds_check",  bounds_check_node)
    g.add_node("rules_engine",  rules_engine_node)
    g.add_node("ai_assessor",   ai_assessor_node)
    g.add_node("ai_explainer",  ai_explainer_node)
    g.add_node("guardrails",    guardrails_node)
    g.add_node("auto_decision", auto_decision_node)
    g.add_node("human_in_loop", human_in_loop_node)
    g.add_node("finalize",      finalize_node)

    g.set_entry_point("ingest")

    g.add_conditional_edges("ingest", route_after_ingest,
                            {"bounds_check": "bounds_check", "human_in_loop": "human_in_loop"})

    # bounds_check corre ANTES de la rama ai_assessor/ai_explainer — ver docstring
    # de bounds_check.py: no depende de revalidation_result ni de ai_assessment.
    g.add_edge("bounds_check", "rules_engine")

    g.add_conditional_edges("rules_engine", route_after_rules,
                            {"ai_assessor": "ai_assessor", "ai_explainer": "ai_explainer"})

    g.add_edge("ai_assessor",  "ai_explainer")
    g.add_edge("ai_explainer", "guardrails")

    g.add_conditional_edges("guardrails", route_after_guardrails,
                            {"auto_decision": "auto_decision", "human_in_loop": "human_in_loop"})

    g.add_edge("auto_decision", "finalize")
    g.add_edge("human_in_loop", "finalize")
    g.add_edge("finalize",      END)

    return g.compile()


credit_graph = build_graph()


async def run_decision(customer: dict, offer: dict, selected_amount: float) -> dict:
    decision_id = str(uuid.uuid4())

    initial_state: CreditState = {
        "decision_id":         decision_id,
        "customer":            customer,
        "offer":               offer,
        "selected_amount":     selected_amount,
        "revalidation_result": {},
        "ai_assessment":       {},
        "ai_explanation":      {},
        "guardrail_flags":     [],
        "route":               "auto",
        "human_resolution":    {},
        "final_decision":      {},
        "trace":               [],
        "started_at":          time.time(),
    }

    logger.info("run_decision | starting | id=%s | customer=%s | offer=%s",
                decision_id, customer.get("customer_id"), offer.get("offer_id"))

    final_state = await credit_graph.ainvoke(initial_state)

    return {
        "decision_id":     decision_id,
        "outcome":         final_state["final_decision"].get("outcome"),
        "approved_amount": final_state["final_decision"].get("approved_amount"),
        "notice_type":     final_state["final_decision"].get("notice_type"),
        "persisted":       final_state["final_decision"].get("persisted", True),
        "explanation":     final_state.get("ai_explanation", {}),
        "latency_ms":      final_state["final_decision"].get("latency_ms"),
        "route":           final_state.get("route"),
        "guardrail_flags": final_state.get("guardrail_flags", []),
        "trace":           final_state.get("trace", []),
    }
