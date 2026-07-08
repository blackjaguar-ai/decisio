"""
bounds_check — G1 (bounds de monto) + G4 (inputs anómalos), corridos ANTES
de ai_explainer. Ninguno de los dos depende de `revalidation_result` ni de
`ai_assessment` — son validaciones de integridad del payload, no juicios
sobre el perfil de riesgo del cliente ni sobre el razonamiento de la AI.

Fix #2 (original): staleness/tampering de monto vivían en `guardrails`, que
corre DESPUÉS de `ai_explainer`. Resultado: `ai_explainer` narraba "se honra
la oferta" y guardrails lo contradecía dos nodos después.

Fix #2.1 (encontrado tras retesteo en el VPS real): el mismo defecto seguía
vivo para G4. El perfil `anomalous_inputs` mostró `ai_explainer` diciendo
"se honra tal como fue comunicada" mientras `guardrails` lo escalaba a
humano por desproporción monto/ingreso — porque G4 seguía viviendo en el
nodo final. G4 tampoco depende de ai_assessment, así que no había razón
estructural para dejarlo ahí. Se mueve aquí junto con G1.

G2 (coherencia regla-AI) y G3 (confianza mínima) SÍ se quedan en `guardrails`
— esos necesitan `ai_assessment`, que en este punto del grafo todavía no existe.
"""

import logging
import os
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

INCOME_DISPROPORTION_MULTIPLE = float(os.getenv("INCOME_DISPROPORTION_MULTIPLE", "20"))


def bounds_check_node(state: CreditState) -> dict:
    customer = state["customer"]
    offer    = state["offer"]
    selected = state.get("selected_amount", 0)
    flags: list[dict] = []

    # G1 — Bounds de monto.
    floor            = offer.get("floor_amount", 0)
    cap_at_offer     = offer.get("cap_at_offer_time", 0)
    cap_at_execution = offer.get("cap_at_execution_time", cap_at_offer)

    # Tampering: el monto no corresponde a ningún tope emitido para este cliente.
    if selected < floor or selected > cap_at_offer:
        flags.append({"guardrail": "tampering", "severity": "hard",
                      "message": f"S/{selected:,.0f} no corresponde a ningún tope emitido para este "
                                 f"cliente (rango ofertado: S/{floor:,.0f}–S/{cap_at_offer:,.0f})."})
    # Staleness: el tope vigente bajó desde que se renderizó la oferta — condición
    # de carrera normal, sin ataque de por medio. Mismo guardrail conceptual, flag distinto.
    elif selected > cap_at_execution:
        flags.append({"guardrail": "staleness", "severity": "hard",
                      "message": f"El tope vigente al ejecutar (S/{cap_at_execution:,.0f}) bajó respecto "
                                 f"al que se mostró en la oferta (S/{cap_at_offer:,.0f}). Se bloquea el "
                                 f"monto anterior y se informa el tope actualizado."})

    # G4 — Inputs anómalos (posible sesgo en datos, Res. SBS 053-2023).
    #
    # dti_ratio<0, credit_score>999, tenure_months<0 ya son rechazados por Pydantic
    # (CustomerProfile) antes de llegar aquí si el caller entra por POST /decision —
    # se mantienen como defensa en profundidad para cualquier caller que invoque
    # run_decision() directo, sin pasar por el schema HTTP.
    #
    # La desproporción monto/ingreso SÍ es alcanzable por la API real: es una
    # inconsistencia ENTRE campos, no un rango de un campo aislado — Pydantic no
    # puede expresarlo con un Field() por columna.
    anomalies = []
    if customer.get("dti_ratio", 0) < 0:        anomalies.append("dti_ratio negativo")
    if customer.get("credit_score", 500) > 999: anomalies.append("credit_score fuera de rango")
    if customer.get("tenure_months", 0) < 0:    anomalies.append("antigüedad negativa")
    if selected <= 0:                           anomalies.append("monto seleccionado <= 0")

    monthly_income = customer.get("monthly_income")
    if monthly_income and selected > monthly_income * INCOME_DISPROPORTION_MULTIPLE:
        anomalies.append(
            f"monto seleccionado (S/{selected:,.0f}) es {selected / monthly_income:.0f}x el "
            f"ingreso mensual declarado (S/{monthly_income:,.0f})"
        )

    if anomalies:
        flags.append({"guardrail": "anomalous_inputs", "severity": "hard",
                      "message": f"Inputs inconsistentes: {', '.join(anomalies)}."})

    if flags:
        logger.warning("bounds_check | %s | flags=%d", state["decision_id"], len(flags))
    else:
        logger.info("bounds_check | %s | ok", state["decision_id"])

    return {
        "guardrail_flags": flags,
        "trace": state["trace"] + [{"step": "bounds_check", "flags": flags}],
    }
