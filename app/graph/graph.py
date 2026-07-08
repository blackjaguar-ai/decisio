"""
Grafo LangGraph — DECISIO Motor de Revalidación de Oferta Firme.
3 rutas reales + 1 corte temprano por payload incompleto + 1 gate de
identidad previo (fuera del grafo, ver app/api/routes/decision.py).

Semana 2: el grafo ahora compila CON checkpointer (AsyncPostgresSaver), lo
que habilita interrupt()/Command(resume=...) real en human_in_loop.py. La
compilación se pospone a init_graph() — llamada desde el lifespan de FastAPI
DESPUÉS de que exista el pool de Postgres — porque el checkpointer necesita
una conexión real para correr su setup() de migraciones. Compilar en tiempo
de import (como en Semana 1) ya no es posible.
"""

import time
import uuid
import logging
from langgraph.graph import StateGraph, END
from langgraph.types import Command

from app.graph.state import CreditState
from app.graph.checkpointer import get_checkpointer
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
    Fix #3 (heredado): un payload incompleto se corta directo a human_in_loop —
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


# ── Build (sin compilar — la compilación necesita el checkpointer) ─────────────

def _build_graph() -> StateGraph:
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

    return g


_graph_builder = _build_graph()
_compiled_graph = None  # se compila en init_graph(), después de init_checkpointer()


async def init_graph():
    """Llamar en el lifespan de FastAPI, DESPUÉS de checkpointer.init_checkpointer()."""
    global _compiled_graph
    checkpointer = get_checkpointer()
    _compiled_graph = _graph_builder.compile(checkpointer=checkpointer)
    logger.info("graph | compilado con checkpointer Postgres — interrupt()/resume habilitado")


def get_graph():
    if _compiled_graph is None:
        raise RuntimeError("Grafo no compilado — llamar init_graph() en el startup de la app")
    return _compiled_graph


def _thread_config(decision_id: str) -> dict:
    return {"configurable": {"thread_id": decision_id}}


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

    final_state = await get_graph().ainvoke(initial_state, config=_thread_config(decision_id))

    # Semana 2: el grafo puede volver PAUSADO (interrupt() disparado dentro de
    # human_in_loop) en vez de terminado. LangGraph señaliza esto con la key
    # "__interrupt__" en el dict de retorno — `final_decision` todavía no
    # existe en el state porque human_in_loop no ha terminado de ejecutar.
    if "__interrupt__" in final_state:
        explanation = final_state.get("ai_explanation", {})
        latency_ms = int((time.time() - initial_state["started_at"]) * 1000)
        logger.info("run_decision | %s | paused for human review | elapsed=%dms",
                    decision_id, latency_ms)
        return {
            "decision_id":     decision_id,
            "outcome":         "pending_human",
            "approved_amount": None,
            "notice_type":     explanation.get("notice_type"),
            "persisted":       True,  # placeholder en `decisions` + `cases` ya escritos
            "explanation":     explanation,
            "latency_ms":      latency_ms,
            "route":           "human",
            "guardrail_flags": final_state.get("guardrail_flags", []),
            "trace":           final_state.get("trace", []) + [
                {"step": "human_in_loop", "status": "escalated_pending"}
            ],
        }

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


async def resolve_case(decision_id: str, resolution: dict) -> dict:
    """
    Reanuda un grafo pausado en human_in_loop con la resolución del agente.
    `resolution` es el .model_dump() de CaseResolutionRequest — llega intacto
    al `interrupt()` que lo está esperando dentro del nodo.
    """
    logger.info("resolve_case | %s | resuming with resolution=%s", decision_id, resolution)

    final_state = await get_graph().ainvoke(
        Command(resume=resolution), config=_thread_config(decision_id)
    )

    if "__interrupt__" in final_state:
        # No debería pasar nunca en este grafo (un solo interrupt por caso) —
        # defensivo: mejor un 500 explícito que devolver un estado a medias.
        raise RuntimeError(
            f"El grafo volvió a pausarse tras resume para {decision_id} — estado inesperado."
        )

    final_decision = final_state.get("final_decision", {})
    return {
        "decision_id":     decision_id,
        "outcome":         final_decision.get("outcome"),
        "approved_amount": final_decision.get("approved_amount"),
        "notice_type":     final_decision.get("notice_type"),
        "persisted":       final_decision.get("persisted", True),
        "explanation":     final_state.get("ai_explanation", {}),
        "latency_ms":      final_decision.get("latency_ms"),
        "route":           final_state.get("route"),
        "guardrail_flags": final_state.get("guardrail_flags", []),
        "trace":           final_state.get("trace", []),
    }
