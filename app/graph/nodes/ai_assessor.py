"""
ai_assessor — corre SOLO cuando rules_engine devuelve hallazgo_menor.

No evalúa una solicitud nueva. Razona sobre una pregunta acotada: dado este
cambio puntual detectado desde que se generó la oferta, ¿se sigue honrando
tal como está, se ajusta el monto, o se escala? Nunca ejecuta — recomienda.
El humano decide siempre en hallazgo_menor (ver routing en graph.py).
"""

import json
import logging
import os
from anthropic import Anthropic
from app.graph.state import CreditState
from app.graph.nodes._llm_utils import call_llm, parse_llm_json

logger = logging.getLogger(__name__)

LLM_MODEL               = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.70"))

_client = Anthropic(max_retries=0)  # fix #7.1 — el reintento vive solo en call_llm, no apilado

SYSTEM = """Eres un motor de revalidación de ofertas de crédito ya preaprobadas, para un banco
regulado por la SBS de Perú. Analizas casos donde la revalidación determinística encontró un
HALLAZGO MENOR: algo cambió en el perfil del cliente desde que se generó la oferta preaprobada,
pero no lo suficiente para revocarla automáticamente.

REGLAS ABSOLUTAS:
1. Responde ÚNICAMENTE con JSON válido. Sin texto antes ni después. Sin backticks.
2. No inventes datos. Si un dato no está en el perfil, usa null.
3. Tu recomendación es insumo para una decisión humana — tú NUNCA ejecutas la ampliación ni revocas la oferta.
4. No estás evaluando una solicitud nueva. Estás evaluando si un compromiso YA COMUNICADO al
   cliente se sigue sosteniendo dado el hallazgo detectado.
5. Si la confianza es baja o la información es insuficiente, recomienda "escalate_to_human".
6. Nunca insertes saltos de línea dentro de los valores de string. Cada campo es una sola línea
   continua, con palabras separadas por espacios simples — nunca palabras pegadas sin espacio.

FORMATO (exacto):
{
  "recommendation": "honor_offer" | "adjust_amount" | "escalate_to_human",
  "confidence": 0.00,
  "reasoning": "Explicación concisa en español (2-4 oraciones), enfocada en si el hallazgo justifica dejar de honrar la oferta.",
  "key_factors": {
    "positive": ["factor 1", "factor 2"],
    "negative": ["factor 1"],
    "uncertain": ["factor 1"]
  },
  "risk_flags": [],
  "suggested_amount": null
}"""

PROMPT = """Evalúa este hallazgo menor detectado al revalidar una oferta de ampliación de línea ya preaprobada.

PERFIL ACTUAL DEL CLIENTE:
{customer_json}

OFERTA YA COMUNICADA AL CLIENTE:
- Rango ofertado: S/ {floor:,.0f} – S/ {cap:,.0f}
- Monto seleccionado por el cliente: S/ {selected:,.0f}
- Versión de criterios congelados usada para revalidar: {rules_version}

HALLAZGO(S) DETECTADO(S) EN LA REVALIDACIÓN (vs. criterio congelado al momento de la oferta):
{rules_json}"""


def ai_assessor_node(state: CreditState) -> dict:
    customer            = state["customer"]
    offer                = state["offer"]
    selected_amount      = state.get("selected_amount", 0)
    revalidation_result  = state["revalidation_result"]

    prompt = PROMPT.format(
        customer_json=json.dumps(customer, ensure_ascii=False, indent=2),
        floor=offer.get("floor_amount", 0),
        cap=offer.get("cap_at_offer_time", 0),
        selected=selected_amount,
        rules_version=offer.get("rules_version", "N/A"),
        rules_json=json.dumps(revalidation_result.get("triggered_rules", []), ensure_ascii=False, indent=2),
    )

    raw = None
    try:
        raw = call_llm(_client, LLM_MODEL, SYSTEM, prompt, max_tokens=1000,
                       decision_id=state["decision_id"], node="ai_assessor")
        logger.info("ai_assessor | %s | raw_response=%s", state["decision_id"], raw[:500])
        assessment = parse_llm_json(raw)
    except Exception as e:
        logger.error("ai_assessor | %s | error: %s | raw=%s", state["decision_id"], e, raw)
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
