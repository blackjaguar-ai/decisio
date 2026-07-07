"""
Perfiles sintéticos para la demo de iO.
Curados para disparar deliberadamente cada camino del grafo.
En la reunión se recorren en orden — cada uno cuenta una parte de la historia.
"""

PROFILES = {

    # Camino 1 — Aprobación automática limpia
    # "8 segundos. Eso es todo."
    "clean_approval_1": {
        "customer_id": "CLI-001", "name": "Ana Torres Quispe",
        "credit_score": 780, "tenure_months": 24, "dti_ratio": 0.22,
        "max_days_overdue_12m": 0, "requested_amount": 8000.0,
        "preapproved_limit": 12000.0, "monthly_income": 5500.0,
    },
    "clean_approval_2": {
        "customer_id": "CLI-002", "name": "Roberto Sánchez Llanos",
        "credit_score": 720, "tenure_months": 18, "dti_ratio": 0.35,
        "max_days_overdue_12m": 0, "requested_amount": 5000.0,
        "preapproved_limit": 7000.0, "monthly_income": 4200.0,
    },

    # Camino 2 — Zona gris: AI razona, escala a humano
    # "La AI no decide el dinero sola."
    "gray_zone_1": {
        "customer_id": "CLI-003", "name": "Carmen Flores Medina",
        "credit_score": 670, "tenure_months": 9, "dti_ratio": 0.44,
        "max_days_overdue_12m": 15, "requested_amount": 6000.0,
        "preapproved_limit": 8000.0, "monthly_income": 3800.0,
    },
    "gray_zone_2": {
        "customer_id": "CLI-004", "name": "Diego Vargas Chávez",
        "credit_score": 690, "tenure_months": 7, "dti_ratio": 0.47,
        "max_days_overdue_12m": 0, "requested_amount": 7500.0,
        "preapproved_limit": 10000.0, "monthly_income": 4500.0,
    },

    # Camino 3 — Monto alto: HITL obligatorio por política
    # "Sin importar el perfil, el humano valida los montos grandes."
    "high_amount": {
        "customer_id": "CLI-005", "name": "Patricia Mendoza Lagos",
        "credit_score": 810, "tenure_months": 36, "dti_ratio": 0.18,
        "max_days_overdue_12m": 0, "requested_amount": 15000.0,
        "preapproved_limit": 12000.0, "monthly_income": 8000.0,
    },

    # Camino 4 — Rechazo duro
    # "Las reglas mandan. La AI explica el rechazo, no lo revierte."
    "hard_rejection": {
        "customer_id": "CLI-006", "name": "Luis Romero Pizarro",
        "credit_score": 580, "tenure_months": 3, "dti_ratio": 0.62,
        "max_days_overdue_12m": 45, "requested_amount": 4000.0,
        "preapproved_limit": 5000.0, "monthly_income": 2200.0,
    },

    # Camino 5 — Inputs anómalos: guardrails en acción
    # "El sistema detecta inconsistencias y las escala. No las procesa."
    "anomalous": {
        "customer_id": "CLI-007", "name": "Test Anómalo",
        "credit_score": 1200, "tenure_months": -2, "dti_ratio": -0.15,
        "max_days_overdue_12m": 0, "requested_amount": 5000.0,
        "preapproved_limit": 5000.0, "monthly_income": 3000.0,
    },
}
