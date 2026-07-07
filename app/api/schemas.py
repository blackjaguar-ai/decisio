from pydantic import BaseModel, Field


class CustomerProfile(BaseModel):
    customer_id:          str
    name:                 str
    credit_score:         int   = Field(ge=300, le=900)
    tenure_months:        int   = Field(ge=0)
    dti_ratio:            float = Field(ge=0.0, le=2.0)
    max_days_overdue_12m: int   = Field(ge=0)
    requested_amount:     float = Field(gt=0)
    preapproved_limit:    float = Field(gt=0)
    monthly_income:       float | None = None
    product_type:         str   = "credit_line_increase"
    additional_context:   dict  | None = None


class DecisionRequest(BaseModel):
    customer: CustomerProfile


class DecisionResponse(BaseModel):
    decision_id:     str
    outcome:         str
    approved_amount: float | None
    explanation:     dict
    latency_ms:      int | None
    route:           str
    guardrail_flags: list
    trace:           list
