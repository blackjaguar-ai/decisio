"""
checkpointer — Semana 2. AsyncPostgresSaver sobre el MISMO AsyncConnectionPool
que usan las tablas de negocio (app/db/connection.py). Un solo pool, un solo
driver psycopg v3 — misma decisión de arquitectura que ya regía para el resto
del proyecto (Roadmap §9.bis: "un solo driver = coherencia total").

Esto es la pieza marcada como "integración de alto riesgo a validar temprano"
en el handoff. Antes de escribir este archivo se validó en sandbox, contra
Postgres real (no mocks):

1. `AsyncPostgresSaver(conn=pool)` acepta un `AsyncConnectionPool` directamente
   -- confirmado leyendo `langgraph.checkpoint.postgres._ainternal.get_connection`,
   que hace `async with pool.connection() as conn` igual que
   `app/db/connection.py`. No hace falta un segundo pool ni una conexión
   dedicada.
2. El pool DEBE abrirse con `autocommit=True` (ver connection.py) -- sin esto,
   `checkpointer.setup()` revienta: sus migraciones internas corren
   `CREATE INDEX CONCURRENTLY`, que Postgres prohíbe dentro de una transacción
   explícita.
3. El ciclo completo `interrupt()` -> pausa -> `Command(resume=...)` se probó
   con DOS pools/checkpointers distintos apuntando al mismo Postgres --
   simulando un restart real del contenedor `app` -- y el estado pausado
   sobrevivió intacto. Esto es lo que hace seguro perder el proceso de FastAPI
   con un caso `pending_human` a medio resolver.
"""

import logging
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.db import connection as db

logger = logging.getLogger(__name__)

_checkpointer: AsyncPostgresSaver | None = None


async def init_checkpointer() -> AsyncPostgresSaver:
    """Llamar UNA vez en el lifespan de FastAPI, después de db.init_pool()."""
    global _checkpointer
    pool = db.get_pool()
    _checkpointer = AsyncPostgresSaver(conn=pool)
    await _checkpointer.setup()  # idempotente — CREATE TABLE/INDEX IF NOT EXISTS por dentro
    logger.info("checkpointer | AsyncPostgresSaver.setup() OK — tablas de checkpoint listas")
    return _checkpointer


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer no inicializado — llamar init_checkpointer() en el startup")
    return _checkpointer
