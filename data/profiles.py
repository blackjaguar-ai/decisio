"""
Perfiles sintéticos para la demo de iO — DECISIO revalida ofertas ya
preaprobadas, no evalúa solicitudes nuevas. Cada perfil trae customer + offer
+ selected_amount + identity_verified, listo para mandarse tal cual al body
de POST /decision.

Curados para disparar deliberadamente cada ruta real del grafo (Spec §10) —
nada de rutas inventadas. En la reunión se recorren en orden.
"""

from copy import deepcopy

DEFAULT_CRITERIA_SNAPSHOT = {
    "score_threshold":  650,
    "max_dti":          0.40,
    "max_dti_gray":     0.50,
    "min_tenure_months": 6,
}


def _offer(offer_id: str, floor: float, cap_offer: float, *,
           rules_version: str = "v2026.05.12",
           criteria_snapshot: dict | None = None,
           cap_execution: float | None = None,
           generated_at: str = "2026-06-01T09:00:00Z") -> dict:
    return {
        "offer_id": offer_id,
        "floor_amount": floor,
        "cap_at_offer_time": cap_offer,
        "cap_at_execution_time": cap_execution if cap_execution is not None else cap_offer,
        "offer_generated_at": generated_at,
        "rules_version": rules_version,
        "criteria_snapshot": criteria_snapshot or deepcopy(DEFAULT_CRITERIA_SNAPSHOT),
    }


PROFILES = {

    # 1 — Camino limpio (dominante). Nada cambió desde el batch. "8 segundos. Eso es todo."
    "clean_approval_1": {
        "customer": {
            "customer_id": "CLI-001", "name": "Ana Torres Quispe",
            "credit_score": 780, "tenure_months": 24, "dti_ratio": 0.22,
            "max_days_overdue_12m": 0, "monthly_income": 5500.0,
        },
        "offer": _offer("OFR-001", floor=8000.0, cap_offer=12000.0),
        "selected_amount": 12000.0,
        "identity_verified": True,
    },

    # 2 — Camino limpio, con rules_version desactualizada respecto a una política
    #     "vigente" hipotética más estricta. Se revalida contra la versión congelada
    #     (v2026.03.01, max_dti=40%) y se honra igual — responde en vivo la objeción
    #     de Legal sobre cambios de política a mitad de camino (doctrina firm offer).
    "clean_approval_2_pinned_policy": {
        "customer": {
            "customer_id": "CLI-002", "name": "Roberto Sánchez Llanos",
            "credit_score": 720, "tenure_months": 18, "dti_ratio": 0.37,
            "max_days_overdue_12m": 0, "monthly_income": 4200.0,
        },
        "offer": _offer("OFR-002", floor=3000.0, cap_offer=7000.0,
                        rules_version="v2026.03.01"),
        "selected_amount": 5000.0,
        "identity_verified": True,
    },

    # 3 — Hallazgo menor: DTI subió a zona gris desde el batch. ai_assessor razona,
    #     escala siempre a human_in_loop (nunca decide solo).
    "gray_zone_dti": {
        "customer": {
            "customer_id": "CLI-003", "name": "Carmen Flores Medina",
            "credit_score": 670, "tenure_months": 9, "dti_ratio": 0.44,
            "max_days_overdue_12m": 0, "monthly_income": 3800.0,
        },
        "offer": _offer("OFR-003", floor=4000.0, cap_offer=8000.0),
        "selected_amount": 6000.0,
        "identity_verified": True,
    },

    # 4 — Hallazgo menor: mora leve posteada después del batch, bajo el umbral duro.
    "gray_zone_mora": {
        "customer": {
            "customer_id": "CLI-004", "name": "Diego Vargas Chávez",
            "credit_score": 690, "tenure_months": 7, "dti_ratio": 0.30,
            "max_days_overdue_12m": 15, "monthly_income": 4500.0,
        },
        "offer": _offer("OFR-004", floor=5000.0, cap_offer=10000.0),
        "selected_amount": 7500.0,
        "identity_verified": True,
    },

    # 5 — Hallazgo descalificante duro: score cayó bajo el umbral congelado desde
    #     el batch. Revoca como notice_type=adverse_action. Una sola regla disparada,
    #     sin ai_assessment -> dispara el atajo determinístico de ai_explainer.
    "hard_rejection_score_drop": {
        "customer": {
            "customer_id": "CLI-005", "name": "Luis Romero Pizarro",
            "credit_score": 580, "tenure_months": 12, "dti_ratio": 0.30,
            "max_days_overdue_12m": 0, "monthly_income": 2200.0,
        },
        "offer": _offer("OFR-005", floor=2000.0, cap_offer=5000.0),
        "selected_amount": 4000.0,
        "identity_verified": True,
    },

    # 6 — Gate de identidad (§6.bis): falla antes de tocar el grafo. run_decision
    #     nunca se invoca — el chequeo vive en app/api/routes/decision.py.
    "identity_mismatch": {
        "customer": {
            "customer_id": "CLI-006", "name": "Patricia Mendoza Lagos",
            "credit_score": 810, "tenure_months": 36, "dti_ratio": 0.18,
            "max_days_overdue_12m": 0, "monthly_income": 8000.0,
        },
        "offer": _offer("OFR-006", floor=10000.0, cap_offer=12000.0),
        "selected_amount": 12000.0,
        "identity_verified": False,
    },

    # 7 — Staleness de monto: el tope vigente al ejecutar bajó respecto al que el
    #     slider mostró al abrir la oferta. Guardrail de bounds en vivo, sin
    #     necesidad de tampering real — dos campos distintos en el perfil.
    "staleness_amount": {
        "customer": {
            "customer_id": "CLI-007", "name": "Elena Ríos Castañeda",
            "credit_score": 740, "tenure_months": 20, "dti_ratio": 0.25,
            "max_days_overdue_12m": 0, "monthly_income": 4800.0,
        },
        "offer": _offer("OFR-007", floor=6000.0, cap_offer=10000.0, cap_execution=8000.0),
        "selected_amount": 10000.0,  # lo que el cliente vio y eligió en el slider
        "identity_verified": True,
    },

    # 8 (reserva — no forma parte del guion principal) — Inputs anómalos: guardrails
    # detectan una inconsistencia CRUZADA entre campos (monto vs. ingreso declarado)
    # que Pydantic no puede expresar con un Field() por columna, y por eso SÍ llega
    # vivo hasta guardrails.py a diferencia de un valor de rango inválido (ese lo
    # rechaza Pydantic antes con 422). Útil para objeciones de seguridad.
    "anomalous_inputs": {
        "customer": {
            "customer_id": "CLI-008", "name": "Test Desproporción Monto/Ingreso",
            "credit_score": 700, "tenure_months": 12, "dti_ratio": 0.20,
            "max_days_overdue_12m": 0, "monthly_income": 1500.0,
        },
        "offer": _offer("OFR-008", floor=10000.0, cap_offer=50000.0),
        "selected_amount": 45000.0,  # 30x el ingreso mensual declarado -> dispara G4
        "identity_verified": True,
    },
}
