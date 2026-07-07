import json
import logging
import os
from anthropic import Anthropic
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

LLM_MODEL             = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.70"))

_client = Anthropic()

SYSTEM = """Eres un motor de evaluación de riesgo crediticio para un banco regulado por la SBS de Perú.
Analizas casos en ZONA GRIS donde las reglas determinísticas no dieron aprobación ni rechazo definitivo.

REGLAS ABSOLUTAS:
1. Responde ÚNICAMENTE con JSON válido. Sin texto antes ni después. Sin backticks.
2. No inventes datos. Si un dato no está en el perfil, usa null.
3. Tu recomendación es insumo para una decisión humana — tú NO apruebas créditos.
4. Si la confianza es baja o la información es insuficiente, recomienda "escalate_to_human".

FORMATO (exacto):
{
  "recommendation": "approve" | "reject" | "escalate_to_human",
  "confidence": 0.00,
  "reasoning": "Explicación concisa en español (2-4 oraciones).",
  "key_factors": {
    "positive": ["factor 1", "factor 2"],
    "negative": ["factor 1"],
    "uncertain": ["factor 1"]
  },
  "risk_flags": [],
  "suggested_amount": null
}"""

PROMPT = """Evalúa este caso de zona gris para ampliación de línea de crédito.

PERFIL:
{customer_json}

REGLAS DISPARADAS:
{rules_json}

MONTO SOLICITADO: S/ {requested:,.0f}
LÍMITE PREAPROBADO: S/ {preapproved:,.0f}"""


def ai_assessor_node(state: CreditState) -> dict:
    customer = state["customer"]
    rules_result = state["rules_result"]

    prompt = PROMPT.format(
        customer_json=json.dumps(customer, ensure_ascii=False, indent=2),
        rules_json=json.dumps(rules_result["triggered_rules"], ensure_ascii=False, indent=2),
        requested=customer.get("requested_amount", 0),
        preapproved=customer.get("preapproved_limit", 0),
    )

    try:
        response = _client.messages.create(
            model=LLM_MODEL,
            max_tokens=1000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        assessment = json.loads(raw)
    except Exception as e:
        logger.error("ai_assessor | %s | error: %s", state["decision_id"], e)
        assessment = {
            "recommendation": "escalate_to_human",
            "confidence": 0.0,
            "reasoning": f"Error en modelo: {str(e)[:100]}. Caso escalado por seguridad.",
            "key_factors": {"positive": [], "negative": [], "uncertain": []},
            "risk_flags": ["model_error"],
            "suggested_amount": None,
        }

    if assessment.get("confidence", 0) < AI_CONFIDENCE_THRESHOLD:
        assessment["recommendation"] = "escalate_to_human"
        assessment.setdefault("risk_flags", []).append("low_confidence")

    logger.info("ai_assessor | %s | recommendation=%s | confidence=%.2f",
                state["decision_id"], assessment.get("recommendation"), assessment.get("confidence", 0))

    return {
        "ai_assessment": assessment,
        "trace": state["trace"] + [{"step": "ai_assessor",
                                    "recommendation": assessment.get("recommendation"),
                                    "confidence": assessment.get("confidence"),
                                    "reasoning": assessment.get("reasoning")}],
    }
