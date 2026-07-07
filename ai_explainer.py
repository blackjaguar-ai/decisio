import json
import logging
import os
from anthropic import Anthropic
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
_client = Anthropic()

SYSTEM = """Eres el componente de explicabilidad de un motor de crédito bancario regulado por la SBS de Perú.
Generas justificaciones comprensibles sobre decisiones de ampliación de línea de crédito.

REGLAS ABSOLUTAS:
1. Responde ÚNICAMENTE con JSON válido. Sin texto antes ni después. Sin backticks.
2. Lenguaje claro y directo para alguien sin conocimientos financieros.
3. Nunca menciones el nombre del modelo de AI ni detalles técnicos internos.
4. Para rechazos: sé respetuoso, específico y actionable.
5. Para aprobaciones: sé positivo y claro sobre las condiciones.

FORMATO (exacto):
{
  "summary": "1-2 oraciones que resumen la decisión en lenguaje simple.",
  "explanation_for_customer": "3-5 oraciones en lenguaje natural para el cliente.",
  "factors_considered": ["factor 1 en lenguaje simple", "factor 2", "factor 3"],
  "next_steps": "Qué hace el cliente ahora (1-2 oraciones).",
  "compliance_note": "Nota técnica interna para auditoría regulatoria (máx 2 oraciones)."
}"""

PROMPT = """Genera la justificación para esta decisión de crédito.

PERFIL:
{customer_json}

DECISIÓN: {outcome}
MONTO APROBADO: {approved_amount}
REGLAS EVALUADAS:
{rules_json}
{ai_context}"""


def ai_explainer_node(state: CreditState) -> dict:
    customer     = state["customer"]
    rules_result = state["rules_result"]
    ai_assessment = state.get("ai_assessment", {})
    outcome = rules_result.get("outcome", "unknown")

    if outcome == "approved":
        approved_amount = f"S/ {customer.get('requested_amount', 0):,.0f}"
    elif outcome == "rejected":
        approved_amount = "No aplica — solicitud no aprobada"
    else:
        approved_amount = "Pendiente de revisión"

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
        outcome=outcome,
        approved_amount=approved_amount,
        rules_json=json.dumps(rules_result.get("triggered_rules", []), ensure_ascii=False, indent=2),
        ai_context=ai_context,
    )

    try:
        response = _client.messages.create(
            model=LLM_MODEL,
            max_tokens=800,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        explanation = json.loads(raw)
    except Exception as e:
        logger.error("ai_explainer | %s | error: %s", state["decision_id"], e)
        explanation = {
            "summary": "Decisión procesada por el motor automático.",
            "explanation_for_customer": "Su solicitud fue evaluada según los criterios del banco.",
            "factors_considered": ["Historial crediticio", "Capacidad de pago", "Comportamiento de pagos"],
            "next_steps": "Contacte a nuestro equipo de atención si tiene preguntas.",
            "compliance_note": f"Fallback por error en modelo: {str(e)[:100]}",
        }

    logger.info("ai_explainer | %s | outcome=%s", state["decision_id"], outcome)

    return {
        "ai_explanation": explanation,
        "trace": state["trace"] + [{"step": "ai_explainer", "outcome": outcome,
                                    "summary": explanation.get("summary")}],
    }
