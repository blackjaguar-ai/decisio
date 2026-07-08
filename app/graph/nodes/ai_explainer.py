"""
ai_explainer — justificación en lenguaje natural de toda decisión.

Fixes de esta iteración:
1. El artefacto de spacing ("nofue", "deproducto") viene del modelo, no del código
   Python. Fix: `raw` se loguea SIEMPRE, no solo en el except, más una regla
   explícita en el SYSTEM contra palabras concatenadas.
2. Atajo determinístico: 1 sola regla disparada + sin ai_assessment -> template
   Python, cero llamada al LLM.
3. Narrativa consciente de bounds_check: si `bounds_check` ya marcó
   staleness/tampering/anomalous_inputs sobre el monto, este nodo ya NO
   afirma "se honra el monto elegido" para luego ser contradicho por
   guardrails. Antes: `sin_cambios` + monto stale (o desproporción
   monto/ingreso) generaba una explicación que decía "se honra" y un
   resultado final que escalaba a humano — inconsistente frente al cliente
   y frente a Riesgo. El caso de `anomalous_inputs` (G4) se detectó recién
   en retesteo real: G4 vivía en `guardrails` (después de este nodo) hasta
   que se movió junto con G1 a `bounds_check` por el mismo motivo.
4. `call_llm`/`parse_llm_json` (app/graph/nodes/_llm_utils.py): timeout
   explícito + un reintento antes del fallback, y un segundo intento de
   parseo si el modelo agrega texto fuera del JSON pese al SYSTEM.

`notice_type` se calcula en Python a partir del outcome, no se confía en que el
LLM lo derive — es un campo de cumplimiento (DS 115-2025-PCM / Res. SBS
053-2023), no una decisión estilística del modelo.
"""

import json
import logging
import os
from anthropic import Anthropic
from app.graph.state import CreditState
from app.graph.nodes._llm_utils import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
_client = Anthropic(max_retries=0)  # fix #7.1 — el reintento vive solo en call_llm, no apilado

SYSTEM = """Eres el componente de explicabilidad de un motor de crédito bancario regulado por la SBS de Perú.
Generas justificaciones comprensibles sobre si una oferta de ampliación de línea YA COMUNICADA al
cliente se honra o se revoca. No estás evaluando una solicitud nueva.

REGLAS ABSOLUTAS:
1. Responde ÚNICAMENTE con JSON válido. Sin texto antes ni después. Sin backticks.
2. Lenguaje claro y directo para alguien sin conocimientos financieros.
3. Nunca menciones el nombre del modelo de AI ni detalles técnicos internos.
4. Para revocaciones: sé respetuoso, específico y no repitas el mismo motivo dos veces.
5. Para ofertas honradas sin observaciones: sé positivo y claro sobre las condiciones.
6. Si el monto está pendiente de validación (te lo indica el prompt explícitamente), nunca
   afirmes que el monto ya fue honrado — dilo como pendiente de confirmación.
7. Nunca insertes saltos de línea dentro de los valores de string. Cada campo es una sola línea continua.
8. Cada palabra va separada por un espacio simple. Nunca concatenes dos palabras sin espacio
   entre ellas (ejemplo de lo que NUNCA debes producir: "nofue", "deproducto"). Revisa tu propio
   JSON antes de responder y corrige cualquier palabra pegada.

FORMATO (exacto):
{
  "summary": "1-2 oraciones que resumen la decisión en lenguaje simple.",
  "explanation_for_customer": "3-5 oraciones en lenguaje natural para el cliente.",
  "factors_considered": ["factor 1 en lenguaje simple", "factor 2", "factor 3"],
  "next_steps": "Qué hace el cliente ahora (1-2 oraciones).",
  "compliance_note": "Nota técnica interna para auditoría regulatoria (máx 2 oraciones)."
}"""

PROMPT = """Genera la justificación para esta revalidación de oferta de crédito.

PERFIL ACTUAL DEL CLIENTE:
{customer_json}

RESULTADO DE LA REVALIDACIÓN: {outcome_label}
MONTO: {approved_amount}
HALLAZGOS DETECTADOS EN LA REVALIDACIÓN (vs. criterio congelado al momento de la oferta):
{rules_json}
{bounds_context}
{ai_context}"""

OUTCOME_LABELS = {
    "sin_cambios":             "sin cambios detectados desde el batch — la oferta se honra",
    "hallazgo_descalificante": "hallazgo descalificante — la oferta ya comunicada se revoca",
    "hallazgo_menor":          "hallazgo menor — pendiente de resolución humana",
}

BOUNDS_FLAG_TYPES = {"staleness", "tampering", "anomalous_inputs"}


def _deterministic_explanation(rule: dict, notice_type: str | None) -> dict:
    reason = rule.get("reason", "")
    return {
        "summary": f"La ampliación ofrecida no se puede honrar: {reason}.",
        "explanation_for_customer": (
            f"Al confirmar la ampliación que le ofrecimos, revalidamos su perfil y detectamos un "
            f"cambio desde que se generó la oferta: {reason}. Por esta razón no podemos ejecutar "
            f"la ampliación en este momento."
        ),
        "factors_considered": [reason],
        "next_steps": "Puede contactar a soporte si considera que esta información no es correcta.",
        "compliance_note": (
            f"Regla disparada en revalidación: {rule.get('rule')}. "
            f"Criterio congelado usado: {rule.get('threshold')}."
        ),
        "notice_type": notice_type,
    }


def ai_explainer_node(state: CreditState) -> dict:
    customer            = state["customer"]
    selected_amount      = state.get("selected_amount", 0)
    revalidation_result  = state["revalidation_result"]
    ai_assessment        = state.get("ai_assessment", {})
    outcome              = revalidation_result.get("outcome", "unknown")
    triggered_rules      = revalidation_result.get("triggered_rules", [])

    # Flags de bounds_check (staleness/tampering), calculados ANTES de este nodo.
    bounds_flags = [f for f in state.get("guardrail_flags", []) if f.get("guardrail") in BOUNDS_FLAG_TYPES]

    notice_type = "adverse_action" if outcome == "hallazgo_descalificante" else None

    # Atajo determinístico — una sola regla disparada, sin razonamiento AI de por medio.
    # No interactúa con bounds_flags: un hallazgo descalificante de una sola regla
    # revoca la oferta de todas formas, con o sin problema de monto adicional.
    if len(triggered_rules) == 1 and not ai_assessment:
        explanation = _deterministic_explanation(triggered_rules[0], notice_type)
        logger.info("ai_explainer | %s | deterministic shortcut | rule=%s",
                    state["decision_id"], triggered_rules[0].get("rule"))
        return {
            "ai_explanation": explanation,
            "trace": state["trace"] + [{"step": "ai_explainer", "outcome": outcome,
                                        "summary": explanation.get("summary"), "mode": "deterministic"}],
        }

    if outcome == "sin_cambios" and not bounds_flags:
        approved_amount_label = f"S/ {selected_amount:,.0f}"
    elif outcome == "sin_cambios" and bounds_flags:
        approved_amount_label = "Pendiente de validación de monto — ver detalle de guardrails"
    elif outcome == "hallazgo_descalificante":
        approved_amount_label = "No aplica — oferta revocada"
    else:
        approved_amount_label = "Pendiente de revisión (hallazgo menor, escalado a agente)"

    bounds_context = ""
    if bounds_flags:
        bounds_context = (
            "\nVALIDACIÓN DE MONTO: se detectó una observación sobre el monto seleccionado "
            "(" + ", ".join(f["guardrail"] for f in bounds_flags) + "). NO afirmes que el monto "
            "ya fue ejecutado — descríbelo como pendiente de confirmación del tope vigente."
        )

    ai_context = ""
    if ai_assessment:
        ai_context = f"""
ANÁLISIS AI:
- Recomendación: {ai_assessment.get('recommendation', 'N/A')}
- Confianza: {ai_assessment.get('confidence', 0):.0%}
- Factores positivos: {', '.join(ai_assessment.get('key_factors', {}).get('positive', []))}
- Factores negativos: {', '.join(ai_assessment.get('key_factors', {}).get('negative', []))}"""

    prompt = PROMPT.format(
        customer_json=json.dumps(customer, ensure_ascii=False, indent=2),
        outcome_label=OUTCOME_LABELS.get(outcome, outcome),
        approved_amount=approved_amount_label,
        rules_json=json.dumps(triggered_rules, ensure_ascii=False, indent=2),
        bounds_context=bounds_context,
        ai_context=ai_context,
    )

    raw = None
    try:
        raw = call_llm(_client, LLM_MODEL, SYSTEM, prompt, max_tokens=800,
                       decision_id=state["decision_id"], node="ai_explainer")
        # Loguear SIEMPRE, éxito o no — es la única forma de confirmar el patrón de
        # spacing en producción sobre 20-30 decisiones reales, no solo cuando falla.
        logger.info("ai_explainer | %s | raw_response=%s", state["decision_id"], raw[:800])
        explanation = parse_llm_json(raw)
    except Exception as e:
        logger.error("ai_explainer | %s | error: %s | raw=%s", state["decision_id"], e, raw)
        explanation = {
            "summary": "Decisión procesada por el motor automático.",
            "explanation_for_customer": "Su ampliación fue revalidada según los criterios con los que se le ofreció.",
            "factors_considered": ["Historial crediticio", "Capacidad de pago", "Comportamiento de pagos"],
            "next_steps": "Contacte a nuestro equipo de atención si tiene preguntas.",
            "compliance_note": f"Fallback por error en modelo: {str(e)[:100]}",
        }

    explanation["notice_type"] = notice_type

    logger.info("ai_explainer | %s | outcome=%s", state["decision_id"], outcome)

    return {
        "ai_explanation": explanation,
        "trace": state["trace"] + [{"step": "ai_explainer", "outcome": outcome,
                                    "summary": explanation.get("summary"), "mode": "llm"}],
    }
