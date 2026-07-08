/**
 * Espejo de /data/profiles.py — MISMOS valores exactos (customer/offer/
 * selected_amount), para que la vista cliente simule "tocar la notificación"
 * de cada uno de los 8 perfiles curados que ya se prueban en
 * tests/test_paths.py. Si cambia algo en profiles.py, actualizar aquí.
 *
 * `identityCheckBehavior` no viaja al backend — sólo controla si el paso de
 * verificación de identidad (reingreso de contraseña, §6.bis) debe fallar de
 * forma confiable para el perfil "identity_mismatch" durante la demo en vivo,
 * sin depender de que el presentador tipee algo "mal" a propósito.
 */

const DEFAULT_CRITERIA_SNAPSHOT = {
  score_threshold: 650,
  max_dti: 0.4,
  max_dti_gray: 0.5,
  min_tenure_months: 6,
};

function offer(offer_id, floor_amount, cap_at_offer_time, overrides = {}) {
  return {
    offer_id,
    floor_amount,
    cap_at_offer_time,
    cap_at_execution_time: overrides.cap_execution ?? cap_at_offer_time,
    offer_generated_at: overrides.generated_at ?? "2026-06-01T09:00:00Z",
    rules_version: overrides.rules_version ?? "v2026.05.12",
    criteria_snapshot: overrides.criteria_snapshot ?? { ...DEFAULT_CRITERIA_SNAPSHOT },
  };
}

export const DEMO_PROFILES = [
  {
    key: "clean_approval_1",
    label: "Ana Torres Quispe",
    tag: "Camino limpio",
    tagline: "Nada cambió desde el batch — se honra en segundos.",
    customer: {
      customer_id: "CLI-001", name: "Ana Torres Quispe",
      credit_score: 780, tenure_months: 24, dti_ratio: 0.22,
      max_days_overdue_12m: 0, monthly_income: 5500.0,
    },
    offer: offer("OFR-001", 8000.0, 12000.0),
    selected_amount: 12000.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "clean_approval_2_pinned_policy",
    label: "Roberto Sánchez Llanos",
    tag: "Camino limpio · criterio pineado",
    tagline: "La política \"vigente\" cambió, pero se revalida contra la congelada.",
    customer: {
      customer_id: "CLI-002", name: "Roberto Sánchez Llanos",
      credit_score: 720, tenure_months: 18, dti_ratio: 0.37,
      max_days_overdue_12m: 0, monthly_income: 4200.0,
    },
    offer: offer("OFR-002", 3000.0, 7000.0, { rules_version: "v2026.03.01" }),
    selected_amount: 5000.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "gray_zone_dti",
    label: "Carmen Flores Medina",
    tag: "Hallazgo menor · DTI",
    tagline: "El DTI subió a zona gris — escala a un agente, nunca decide sola la AI.",
    customer: {
      customer_id: "CLI-003", name: "Carmen Flores Medina",
      credit_score: 670, tenure_months: 9, dti_ratio: 0.44,
      max_days_overdue_12m: 0, monthly_income: 3800.0,
    },
    offer: offer("OFR-003", 4000.0, 8000.0),
    selected_amount: 6000.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "gray_zone_mora",
    label: "Diego Vargas Chávez",
    tag: "Hallazgo menor · mora leve",
    tagline: "Mora leve posterior al batch, bajo el umbral duro — va a revisión.",
    customer: {
      customer_id: "CLI-004", name: "Diego Vargas Chávez",
      credit_score: 690, tenure_months: 7, dti_ratio: 0.30,
      max_days_overdue_12m: 15, monthly_income: 4500.0,
    },
    offer: offer("OFR-004", 5000.0, 10000.0),
    selected_amount: 7500.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "hard_rejection_score_drop",
    label: "Luis Romero Pizarro",
    tag: "Hallazgo descalificante",
    tagline: "El score cayó bajo el umbral congelado — la oferta se revoca.",
    customer: {
      customer_id: "CLI-005", name: "Luis Romero Pizarro",
      credit_score: 580, tenure_months: 12, dti_ratio: 0.30,
      max_days_overdue_12m: 0, monthly_income: 2200.0,
    },
    offer: offer("OFR-005", 2000.0, 5000.0),
    selected_amount: 4000.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "identity_mismatch",
    label: "Patricia Mendoza Lagos",
    tag: "Gate de identidad",
    tagline: "La verificación falla — el grafo nunca corre, el core nunca se toca.",
    customer: {
      customer_id: "CLI-006", name: "Patricia Mendoza Lagos",
      credit_score: 810, tenure_months: 36, dti_ratio: 0.18,
      max_days_overdue_12m: 0, monthly_income: 8000.0,
    },
    offer: offer("OFR-006", 10000.0, 12000.0),
    selected_amount: 12000.0,
    identityCheckBehavior: "always_fail",
  },
  {
    key: "staleness_amount",
    label: "Elena Ríos Castañeda",
    tag: "Staleness de monto",
    tagline: "El tope bajó entre que se mostró la oferta y que se ejecuta.",
    customer: {
      customer_id: "CLI-007", name: "Elena Ríos Castañeda",
      credit_score: 740, tenure_months: 20, dti_ratio: 0.25,
      max_days_overdue_12m: 0, monthly_income: 4800.0,
    },
    offer: offer("OFR-007", 6000.0, 10000.0, { cap_execution: 8000.0 }),
    selected_amount: 10000.0,
    identityCheckBehavior: "always_succeed",
  },
  {
    key: "anomalous_inputs",
    label: "Caso de reserva — desproporción monto/ingreso",
    tag: "Inputs anómalos (reserva)",
    tagline: "El monto es 30x el ingreso declarado — objeción de seguridad.",
    customer: {
      customer_id: "CLI-008", name: "Test Desproporción Monto/Ingreso",
      credit_score: 700, tenure_months: 12, dti_ratio: 0.20,
      max_days_overdue_12m: 0, monthly_income: 1500.0,
    },
    offer: offer("OFR-008", 10000.0, 50000.0),
    selected_amount: 45000.0,
    identityCheckBehavior: "always_succeed",
  },
];
