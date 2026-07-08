from typing import TypedDict


class CreditState(TypedDict):
    decision_id: str
    customer: dict              # perfil actual del cliente (revalidación, no evaluación nueva)
    offer: dict                 # {offer_id, floor_amount, cap_at_offer_time, cap_at_execution_time,
                                 #  offer_generated_at, rules_version, criteria_snapshot}
    selected_amount: float      # monto elegido por el cliente en el slider (frontend)
    revalidation_result: dict   # output de rules_engine al re-chequear los criterios congelados del batch
    ai_assessment: dict         # razonamiento AI (solo si revalidation_result trae hallazgo_menor)
    ai_explanation: dict        # justificación en lenguaje natural (incluye notice_type)
    guardrail_flags: list       # violaciones de bounds/staleness/tampering/coherencia
    route: str                  # "auto" | "human"
    human_resolution: dict      # decisión del agente (si HITL)
    final_decision: dict        # decisión final + notice_type
    trace: list                 # log paso a paso
    started_at: float
