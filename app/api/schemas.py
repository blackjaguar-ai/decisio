from pydantic import BaseModel, Field, model_validator


class CriteriaSnapshot(BaseModel):
    """
    Criterio de riesgo congelado al momento del batch que generó la oferta.
    Validado con schema explícito (fix #1): antes era un `dict` suelto — si llegaba
    incompleto, rules_engine.py hacía `.get("max_dti", 0.40)` y usaba el default
    hardcodeado EN SILENCIO, revalidando contra un umbral que nadie congeló. Eso
    contradice el argumento de venta central ("el criterio está pineado, no
    negociable") y es exactamente lo que un examinador SBS encontraría primero.
    Ahora un snapshot incompleto o incoherente se rechaza en el borde de la API
    (422), nunca llega al grafo.
    """
    score_threshold:   int   = Field(gt=0, le=900)
    max_dti:           float = Field(gt=0, le=1)
    max_dti_gray:      float = Field(gt=0, le=1)
    min_tenure_months: int   = Field(ge=0)

    @model_validator(mode="after")
    def _dti_order_is_coherent(self):
        if self.max_dti_gray < self.max_dti:
            raise ValueError(
                f"max_dti_gray ({self.max_dti_gray}) no puede ser menor que "
                f"max_dti ({self.max_dti}) — el criterio congelado es incoherente."
            )
        return self


class OfferSnapshot(BaseModel):
    offer_id:              str
    floor_amount:          float = Field(gt=0)
    cap_at_offer_time:     float = Field(gt=0)
    cap_at_execution_time: float | None = None   # si no llega, se asume == cap_at_offer_time
    offer_generated_at:    str
    rules_version:         str
    criteria_snapshot:     CriteriaSnapshot

    @model_validator(mode="after")
    def _bounds_are_coherent(self):
        # Fix #9 — nada impedía antes que floor_amount > cap_at_offer_time llegara
        # hasta guardrails.py y produjera montos sin sentido. Se rechaza en el borde.
        if self.floor_amount > self.cap_at_offer_time:
            raise ValueError(
                f"floor_amount ({self.floor_amount}) no puede ser mayor que "
                f"cap_at_offer_time ({self.cap_at_offer_time})."
            )
        cap_exec = self.cap_at_execution_time if self.cap_at_execution_time is not None else self.cap_at_offer_time
        if cap_exec < 0:
            raise ValueError("cap_at_execution_time no puede ser negativo.")
        return self


class CustomerProfile(BaseModel):
    customer_id:          str
    name:                 str
    credit_score:         int   = Field(ge=300, le=900)
    tenure_months:        int   = Field(ge=0)
    dti_ratio:            float = Field(ge=0.0, le=2.0)
    max_days_overdue_12m: int   = Field(ge=0)
    account_status:       str   = "active"   # active | blocked | fraud_confirmed | closed
    data_inconsistency:   bool  = False
    monthly_income:       float | None = None
    product_type:         str   = "credit_line_increase"
    additional_context:   dict  | None = None


class DecisionRequest(BaseModel):
    customer:          CustomerProfile
    offer:             OfferSnapshot
    selected_amount:   float = Field(gt=0)

    # Gate de identidad transaccional (§6.bis) — vive antes del grafo, no es un nodo.
    # DEMO: este bool es un proxy de reingreso de contraseña simulado por el frontend.
    # NO es verificación biométrica real. Producción integra el proveedor biométrico
    # de iO/BCP y este campo deja de ser un bool que el cliente manda a ojos cerrados.
    identity_verified: bool = True

    # Idempotencia (fix #8): un retry de red del frontend (típico en móvil con mala
    # señal) no debe ejecutar la ampliación dos veces. Si se manda la misma
    # idempotency_key, se devuelve la respuesta ya calculada sin re-correr el grafo.
    # LIMITACIÓN conocida: esto no cierra la carrera entre dos requests concurrentes
    # con la misma key llegando al mismo tiempo (ambas verían cache-miss) — aceptable
    # para el prototipo, bloqueante para producción real (requeriría lock a nivel DB).
    idempotency_key: str | None = None


class DecisionResponse(BaseModel):
    decision_id:     str
    outcome:         str
    approved_amount: float | None
    notice_type:     str  | None = None
    explanation:     dict
    latency_ms:      int  | None
    route:           str
    guardrail_flags: list
    trace:           list
    persisted:       bool = True   # fix #4 — false si falló la escritura a Postgres
