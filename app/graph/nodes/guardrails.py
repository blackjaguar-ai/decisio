"""
guardrails — G2 (coherencia regla-AI / enum válido), G3 (confianza mínima),
y decisión final de `route`.

Fix #2: los bounds de monto (G1) se movieron a `bounds_check`, que corre
ANTES de `ai_explainer` — este nodo ya no los recalcula, los hereda de
`state["guardrail_flags"]` y los combina con los propios.

Fix #2.1: G4 (inputs anómalos) se movió también a `bounds_check` por el
mismo motivo que G1 — no depende de `ai_assessment` ni de `revalidation_result`,
así que no había razón estructural para dejarlo correr después de
`ai_explainer`. El perfil `anomalous_inputs` mostró la misma contradicción
narrativa que ya se había resuelto para staleness/tampering ("se honra la
oferta" seguido de un escalamiento dos nodos después). Este nodo tampoco lo
recalcula — lo hereda igual que G1.

Fix #5: G2 dejó de ser código muerto. Con el routing actual, `ai_assessor`
solo corre para `hallazgo_menor`, así que el conflicto original ("regla dura +
AI dice honrar") no era alcanzable. Se mantiene como defensa auditable
(Res. SBS 053-2023 exige poder demostrar el override) y se extiende para
cubrir un caso real: una recomendación de AI fuera del enum esperado —
deriva de prompt o JSON corrupto que pasó el parseo pero no el contenido —
que hoy sí puede llegar aquí sin este check.
"""

import logging
import os
from app.graph.state import CreditState

logger = logging.getLogger(__name__)

AI_CONFIDENCE_THRESHOLD = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.70"))
VALID_AI_RECOMMENDATIONS = {"honor_offer", "adjust_amount", "escalate_to_human"}


def guardrails_node(state: CreditState) -> dict:
    revalidation_result  = state["revalidation_result"]
    ai_assessment        = state.get("ai_assessment", {})

    # Hereda los flags de bounds_check (G1: tampering/staleness — G4: anomalous_inputs).
    # No los recalcula.
    flags: list[dict] = list(state.get("guardrail_flags", []))
    force_human = any(f.get("severity") == "hard" for f in flags)

    # G2 — Coherencia regla-AI + validez del enum de recomendación.
    if ai_assessment:
        recommendation = ai_assessment.get("recommendation")
        if revalidation_result.get("outcome") == "hallazgo_descalificante" and recommendation == "honor_offer":
            flags.append({"guardrail": "rule_ai_conflict", "severity": "hard",
                          "message": "La revalidación encontró un hallazgo descalificante pero la AI "
                                     "recomienda honrar la oferta. Escalamiento forzado."})
            force_human = True
        elif recommendation not in VALID_AI_RECOMMENDATIONS:
            flags.append({"guardrail": "invalid_ai_recommendation", "severity": "hard",
                          "message": f"La AI devolvió una recomendación fuera del formato esperado: "
                                     f"'{recommendation}'. Escalamiento forzado por seguridad."})
            force_human = True

    # G3 — Confianza mínima (DS 115-2025-PCM exige supervisión humana ante baja confianza)
    confidence = ai_assessment.get("confidence", 1.0)
    if ai_assessment and confidence < AI_CONFIDENCE_THRESHOLD:
        flags.append({"guardrail": "low_ai_confidence", "severity": "soft",
                      "message": f"Confianza AI {confidence:.0%} bajo umbral {AI_CONFIDENCE_THRESHOLD:.0%}. "
                                 f"DS 115-2025-PCM exige supervisión humana."})
        force_human = True

    base_route = "human" if revalidation_result.get("outcome") == "hallazgo_menor" else "auto"
    final_route = "human" if (force_human or base_route == "human") else "auto"

    if flags:
        logger.warning("guardrails | %s | flags=%d | force_human=%s",
                       state["decision_id"], len(flags), force_human)
    else:
        logger.info("guardrails | %s | all_clear | route=%s", state["decision_id"], final_route)

    return {
        "guardrail_flags": flags,
        "route": final_route,
        "trace": state["trace"] + [{"step": "guardrails", "flags": flags, "route": final_route}],
    }
