import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import connection as db
from app.api.routes import decision, trace, metrics, cases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    logger.info("DECISIO — online")
    yield
    await db.close_pool()
    logger.info("DECISIO — offline")


app = FastAPI(
    title="DECISIO — Motor de Crédito iO",
    version="1.0.0-semana1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    try:
        result = await db.fetch_one("SELECT NOW() as ts")
        return {"status": "ok", "db": str(result["ts"]) if result else "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB unavailable: {e}")


app.include_router(decision.router)
app.include_router(trace.router)
app.include_router(metrics.router)
app.include_router(cases.router)
