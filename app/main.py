import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import connection as db
from app.api.routes import decision, trace, metrics, cases
from app.graph.checkpointer import init_checkpointer
from app.graph.graph import init_graph
from app.logging_config import configure_json_logging

configure_json_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    await init_checkpointer()  # AsyncPostgresSaver.setup() — idempotente
    await init_graph()         # compila el grafo CON checkpointer (interrupt() real)
    logger.info("DECISIO — online (HITL real con interrupt()/AsyncPostgresSaver)")
    yield
    await db.close_pool()
    logger.info("DECISIO — offline")


app = FastAPI(
    title="DECISIO — Motor de Crédito iO",
    version="2.0.0-semana2",
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
