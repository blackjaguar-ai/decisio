import logging
from fastapi import APIRouter, HTTPException
from app.api.schemas import DecisionRequest, DecisionResponse
from app.graph.graph import run_decision

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/decision", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest):
    try:
        result = await run_decision(request.customer.model_dump())
        return DecisionResponse(**result)
    except Exception as e:
        logger.error("POST /decision | error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
