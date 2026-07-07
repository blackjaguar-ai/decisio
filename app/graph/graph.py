"""
Grafo LangGraph — DECISIO Motor de Crédito.
4 caminos para la demo de iO.
"""

import time
import uuid
import logging
from langgraph.graph import StateGraph, END

from app.graph.state import CreditState
from app.graph.nodes.ingest import ingest_node
from app.graph.nodes.rules_engine import rules_engine_node
from app.graph.nodes.ai_assessor import ai_assessor_node
from app.graph.nodes.ai_explainer import ai_explainer_node
from app.graph.nodes.guardrails import guardrails_node
from app.graph.nodes.auto_decision import auto_decision_node
from app.graph.nodes.human_in_loop import human_in_loop_node
from app.graph.nodes.finalize import finalize_node

logger = logging.getLogger(__name__)


# ── Routing ────────────────────────────────────────────────────────────────────

def route_after_rules(state: CreditState) -> str:
    outcome = state["rules_result"].get("outcome", "rejected")
    if outcome == "gray_zone":
        return "ai_assessor"
    return "ai_explainer"


def pre_guardrails_node(state: CreditState) -> dict:
    """Setea route tentativo antes de guardrails, combinando rules + assessor."""
    outcome = state["rules_result"].get("outcome", "rejected")
    ai_rec  = state.get("ai_assessment", {}).get("recommendation", "")

    if outcome == "human_required":
        route = "human"
    elif outcome == "gray_zone":
        route = "human" if ai_rec in ("escalate_to_human", "") else "auto"
    else:
        route = "auto"

    return {
        "route": route,
        "trace": state["trace"] + [{"step": "pre_guardrails",
                                    "rules_outcome": outcome,
                                    "ai_recommendation": ai_rec,
                                    "tentative_route": route}],
    }


def route_after_guardrails(state: CreditState) -> str:
    return "human_in_loop" if state.get("route") == "human" else "auto_decision"


# ── Build ──────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(CreditState)

    g.add_node("ingest",          ingest_node)
    g.add_node("rules_engine",    rules_engine_node)
    g.add_node("ai_assessor",     ai_assessor_node)
    g.add_node("ai_explainer",    ai_explainer_node)
    g.add_node("pre_guardrails",  pre_guardrails_node)
    g.add_node("guardrails",      guardrails_node)
    g.add_node("auto_decision",   auto_decision_node)
    g.add_node("human_in_loop",   human_in_loop_node)
    g.add_node("finalize",        finalize_node)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "rules_engine")

    g.add_conditional_edges("rules_engine", route_after_rules,
                            {"ai_assessor": "ai_assessor", "ai_explainer": "ai_explainer"})

    g.add_edge("ai_assessor",   "ai_explainer")
    g.add_edge("ai_explainer",  "pre_guardrails")
    g.add_edge("pre_guardrails","guardrails")

    g.add_conditional_edges("guardrails", route_after_guardrails,
                            {"auto_decision": "auto_decision", "human_in_loop": "human_in_loop"})

    g.add_edge("auto_decision", "finalize")
    g.add_edge("human_in_loop", "finalize")
    g.add_edge("finalize",      END)

    return g.compile()


credit_graph = build_graph()


async def run_decision(customer: dict) -> dict:
    decision_id = str(uuid.uuid4())

    initial_state: CreditState = {
        "decision_id":    decision_id,
        "customer":       customer,
        "rules_result":   {},
        "ai_assessment":  {},
        "ai_explanation": {},
        "guardrail_flags":[],
        "route":          "auto",
        "human_resolution": {},
        "final_decision": {},
        "trace":          [],
        "started_at":     time.time(),
    }

    logger.info("run_decision | starting | id=%s | customer=%s",
                decision_id, customer.get("customer_id"))

    final_state = await credit_graph.ainvoke(initial_state)

    return {
        "decision_id":    decision_id,
        "outcome":        final_state["final_decision"].get("outcome"),
        "approved_amount":final_state["final_decision"].get("approved_amount"),
        "explanation":    final_state.get("ai_explanation", {}),
        "latency_ms":     final_state["final_decision"].get("latency_ms"),
        "route":          final_state.get("route"),
        "guardrail_flags":final_state.get("guardrail_flags", []),
        "trace":          final_state.get("trace", []),
    }
