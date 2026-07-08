"""
Conexión a Postgres — psycopg v3 async.
Driver único. Un pool, una sintaxis (%s), cero deuda técnica.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import psycopg
import psycopg.rows
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    dsn = os.environ["DATABASE_URL"]
    # autocommit=True (Semana 2, no negociable): AsyncPostgresSaver corre
    # `CREATE INDEX CONCURRENTLY` dentro de sus migraciones internas
    # (checkpointer.setup()), y Postgres PROHÍBE ese DDL dentro de una
    # transacción explícita. Confirmado en sandbox contra Postgres real antes
    # de tocar el VPS: sin esto, setup() revienta con
    # `psycopg.errors.ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot
    # run inside a transaction block`.
    #
    # Esto NO cambia el comportamiento de las queries de negocio: `execute()`,
    # `fetch_one()`, `fetch_all()` de este módulo nunca hacían `conn.commit()`
    # explícito — dependían de que `pool.connection()` haga `async with conn:`
    # por dentro, que commitea al salir del bloque SIN error. Con
    # autocommit=True cada sentencia commitea sola, sin abrir una transacción
    # explícita que envolver — mismo resultado observable, cero riesgo.
    _pool = AsyncConnectionPool(
        conninfo=dsn, min_size=2, max_size=10, open=False,
        kwargs={"autocommit": True},
    )
    await _pool.open()
    logger.info("Postgres pool inicializado (autocommit=True)")


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Postgres pool cerrado")


def get_pool() -> AsyncConnectionPool:
    """Expone el pool crudo para AsyncPostgresSaver (app/graph/checkpointer.py).
    Semana 2: el checkpointer de LangGraph corre sobre el MISMO pool que las
    tablas de negocio — un solo driver psycopg v3, cero segundo pool que
    mantener (misma decisión ya tomada en Roadmap §9.bis)."""
    if _pool is None:
        raise RuntimeError("Pool no inicializado")
    return _pool


@asynccontextmanager
async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    if _pool is None:
        raise RuntimeError("Pool no inicializado")
    async with _pool.connection() as conn:
        yield conn


async def execute(sql: str, params: tuple = ()) -> None:
    async with get_conn() as conn:
        await conn.execute(sql, params)


async def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    async with get_conn() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchone()


async def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    async with get_conn() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql, params)
            return await cur.fetchall()
