from typing import TypedDict


class CreditState(TypedDict):
    decision_id: str
    customer: dict
    rules_result: dict
    ai_assessment: dict
    ai_explanation: dict
    guardrail_flags: list
    route: str
    human_resolution: dict
    final_decision: dict
    trace: list
    started_at: float
